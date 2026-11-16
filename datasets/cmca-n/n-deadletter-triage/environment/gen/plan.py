"""Authoring only, not run by the image build.

    python3 plan.py TASK_DIR

Builds the public tree as the image does, writes tests/truth.json (for every
shipped defect, the messages the shipped release dead-lettered that a replay
with that defect alone fixed does not dead-letter, and the first of them),
draws the verifier's held-out history into tests/hidden, and copies the
reference package, the visible tests and the replay tool into tests/ with
the canary on top. It stops if the history does not have the properties the
walkthrough states, and prints the numbers the walkthrough quotes.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import build  # noqa: E402
import bugs  # noqa: E402
import world  # noqa: E402

CANARY = Path(HERE.parents[3] / "CANARY").read_text(encoding="utf-8").strip()
POISON_DEPLOY = "2027-06-08T11:00:03+00:00"


def day(t: str) -> str:
    return f"2027-09-14T{t}+00:00"


HIDDEN = {
    "seed": 90417,
    "first_id": 500001,
    "start": day("06:00:00"),
    "end": day("18:00:00"),
    "day": (8, 20),
    "rate_day": 4,
    "rate_night": 2,
    "lines": [(1, 20), (3, 15), (6, 12), (10, 10), (14, 10), (18, 8), (24, 6), (30, 5), (40, 4)],
    "skus": 300,
    "versions": {"email.send": [(2, 2), (3, 1)], "refund.issue": [(2, 1), (3, 2)], "invoice.render": [(3, 1)], "stock.sync": [(2, 1), (3, 3)]},
    "stale_idem": (30, 100),
    "refund": (12, 100),
    "refund_delay_min": (5, 120),
    "partial": {"from": day("06:00:00"), "chance": (50, 100), "parts": 3},
    "expired": (4, 100),
    "resend": (4, 100),
    "edit": (3, 100),
    "channel": {"from": day("07:00:00"), "chance": (20, 100), "name": "channel", "value": "kiosk"},
    "extra_fields": [
        {"name": "locale", "from": day("06:00:00"), "types": ["email.send"], "chance": (15, 100), "values": ["de", "fr-CA"]},
        {"name": "coupon", "from": day("10:00:00"), "types": ["refund.issue", "invoice.render"], "chance": (10, 100), "values": ["SPRING", "VIP5"]},
    ],
    "campaign": {"from": day("09:00:00"), "to": day("10:00:00"), "rate": 12, "id": "0914"},
    "poison": [
        {"from": day("11:00:00"), "to": day("11:20:00"), "rate": 1, "kind": "missing"},
        {"from": day("15:00:00"), "to": day("15:15:00"), "rate": 1, "kind": "v1"},
    ],
    "downstream": [
        (day("08:00:00"), "payments", "down", 0),
        (day("08:25:00"), "payments", "ok", 0),
        (day("09:05:00"), "mailer", "throttled", 20),
        (day("09:17:00"), "mailer", "ok", 0),
        (day("09:40:00"), "mailer", "throttled", 20),
        (day("09:50:00"), "mailer", "ok", 0),
        (day("12:00:00"), "payments", "throttled", 60),
        (day("12:15:00"), "payments", "ok", 0),
        (day("13:30:00"), "inventory", "down", 0),
        (day("14:40:00"), "inventory", "ok", 0),
        (day("16:00:00"), "pdfgen", "down", 0),
        (day("16:20:00"), "pdfgen", "ok", 0),
    ],
    "events": [
        (day("06:00:00"), "started config=r101"),
        (day("09:00:00"), "config reload rev=102"),
        (day("10:30:00"), "stopping"),
        (day("10:30:05"), "started config=r102"),
        (day("14:00:00"), "config reload rev=103"),
        (day("16:45:00"), "stopping"),
        (day("16:45:03"), "started config=r103"),
    ],
}

HIDDEN_CONFIGS = {
    "r101": """rev = 101
accept_schema = [2, 3]

[retry]
max_attempts = 5
backoff = "30s"
backoff_max = "10m"

[lease]
visibility = "5m"
heartbeat = true
max_lost = 3

[dedupe]
window = "6h"

[jobs."email.send"]
max_attempts = 7

[jobs."refund.issue"]
max_attempts = 9
backoff = "1m"

[jobs."invoice.render"]
visibility = "90s"
""",
    "r102": """rev = 102
accept_schema = [2, 3]

[lease]
visibility = 300
heartbeat = false
max_lost = 3

[retry]
max_attempts = 5
backoff = "30s"
backoff_max = "10m"

[dedupe]
window = "6h"

[jobs."invoice.render"]
visibility = "4m"

[jobs."refund.issue"]
max_attempts = 9
backoff = "45s"

[jobs."email.send"]
max_attempts = 7
""",
    "r103": """rev = 103
accept_schema = [2, 3]

[lease]
visibility = "5m"
heartbeat = true
max_lost = 2

[retry]
max_attempts = 5
backoff = "30s"
backoff_max = "10m"

[dedupe]
window = "2h"

[jobs."invoice.render"]
visibility = 60

[jobs."stock.sync"]
visibility = "20s"

[jobs."refund.issue"]
max_attempts = 9
backoff = "45s"
backoff_max = "8m"

[jobs."email.send"]
max_attempts = 6
""",
}


def with_canary(text: str, mark: str = "#") -> str:
    return f"{mark} {CANARY.lstrip('# ')}\n{text}"


def copy_with_canary(src: Path, dst: Path, skip=()) -> None:
    for p in sorted(src.rglob("*")):
        if "__pycache__" in p.parts or p.is_dir() or any(s in p.relative_to(src).parts for s in skip):
            continue
        out = dst / p.relative_to(src)
        out.parent.mkdir(parents=True, exist_ok=True)
        if p.suffix == ".json":
            data = json.loads(p.read_text(encoding="utf-8"))
            out.write_text(json.dumps({"canary": CANARY.lstrip("# "), **data}, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        else:
            out.write_text(with_canary(p.read_text(encoding="utf-8")), encoding="utf-8")


def replay_tool(root: Path, pkg_parent: Path, *args: str) -> list[str]:
    r = subprocess.run([sys.executable, "-B", str(root / "tools" / "replay.py"), "--root", str(root), "--pkg", str(pkg_parent), *args],
                       capture_output=True, text=True, check=True)
    return r.stdout.splitlines()


def dead_order(app: Path) -> dict[str, int]:
    lines = [line for log in sorted((app / "logs" / "queue").glob("*.log")) for line in log.read_text(encoding="utf-8").splitlines()]
    return {line.split()[2]: n for n, line in enumerate(lines) if line.split()[1] == "dead-letter"}


def turned(app: Path, pkg_parent: Path, since: str) -> list[tuple[int, str, str]]:
    """(logged time, id, logged reason) of the logged dead letters the package does not dead-letter, in queue log order."""
    order = dead_order(app)
    out = []
    for line in replay_tool(app, pkg_parent, "--since", since, "--diff")[:-1]:
        mid, left, right = line.split()
        if left.startswith("logged=dead-letter:") and not right.startswith("replay=dead-letter"):
            what, when = left.removeprefix("logged=").split("@")
            out.append((world.to_ms(when), mid, what.split(":")[1]))
    return sorted(out, key=lambda x: order[x[1]])


def main() -> int:
    task = Path(sys.argv[1]).resolve()
    tests = task / "tests"
    work = Path(tempfile.mkdtemp())
    app = work / "app"
    subprocess.run([sys.executable, "-B", str(HERE / "build.py"), str(app)], check=True)
    w = build.run_world(work / "w")
    items, outcomes = w["items"], w["played"]["outcomes"]
    starts = [it[0] for it in items if it[3] == "started"]
    deploy_start = min(t for t in starts if t >= w["cut"])
    poison_start = min(t for t in starts if t >= world.to_ms(POISON_DEPLOY))
    since = world.stamp(deploy_start)

    tail = replay_tool(app, app, "--since", since, "--diff")[-1]
    assert tail.endswith(" 0 differ from the log"), tail
    tail = replay_tool(app, app, "--diff")[-1]
    assert not tail.endswith(" 0 differ from the log"), tail
    print("shipped replay from", since, "reproduces the log; from the first started line it does not:", tail)

    msgs = {mid: (at, job, producer, payload) for at, mid, job, producer, payload in w["drawn"]["messages"]}
    dead_after = {mid: o for mid, o in outcomes.items() if o[0].startswith("dead-letter") and o[1] >= deploy_start}
    reasons: dict[str, int] = {}
    for o in dead_after.values():
        r = o[0].split(":")[1]
        reasons[r] = reasons.get(r, 0) + 1
    print(f"messages {len(msgs)}; dead-lettered by 4.2.0 {len(dead_after)}: {dict(sorted(reasons.items()))}")

    truth = {"causes": []}
    found = {}
    for b in bugs.SHIPPED:
        pkg = build.package_tree(work / f"fix-{b}", [x for x in bugs.SHIPPED if x != b]).parent
        got = turned(app, pkg, since)
        found[b] = got
        assert len(got) >= 10, (b, len(got))
        if len(got) > 1 and got[0][0] == got[1][0]:
            print(f"{b}: {got[0][1]} and {got[1][1]} were dead-lettered at the same millisecond; the queue log order decides")
        bug = next(x for x in bugs.BUGS if x[0] == b)
        lines = bugs.accepted_lines(app / "quayside", b)
        truth["causes"].append({"id": b, "class": bug[1], "file": f"quayside/{bug[2]}", "lines": lines, "messages": len(got), "first": got[0][1]})
    correct = build.package_tree(work / "correct", ()).parent
    all_fixed = {mid for _, mid, _ in turned(app, correct, since)}
    single = set().union(*({mid for _, mid, _ in got} for got in found.values()))
    two = all_fixed - single
    assert len(two) >= 30, len(two)
    assert all(mid in dead_after for mid in all_fixed)
    print(f"turned by every defect fixed {len(all_fixed)}, by one fixed {len(single)}, needing two or more fixes {len(two)}, by one fixed but not by all {len(single - all_fixed)}")
    for c in truth["causes"]:
        got = found[c["id"]]
        by_reason: dict[str, int] = {}
        for _, _, r in got:
            by_reason[r] = by_reason.get(r, 0) + 1
        print(f"{c['id']} {c['class']} {c['file']}:{c['lines']} messages={c['messages']} first={c['first']} at {world.stamp(got[0][0])} reasons={by_reason}")

    spec = world.PUBLIC
    first = {b: found[b][0][0] for b in bugs.SHIPPED}
    assert first["B1"] >= world.to_ms("2027-06-08T17:10:00+00:00")
    campaign = world.to_ms(spec["campaign"]["from"])
    b1 = [t for t, _, _ in found["B1"]]
    assert sum(1 for t in b1 if t >= campaign) > 3 * sum(1 for t in b1 if t < campaign)
    print(f"B1 before the newsletter {sum(1 for t in b1 if t < campaign)}, after {sum(1 for t in b1 if t >= campaign)}")
    assert first["B2"] >= world.to_ms(spec["partial"]["from"])
    assert first["B3"] > world.to_ms("2027-06-08T20:00:00+00:00")
    assert first["B4"] >= world.to_ms(spec["channel"]["from"])
    pos = {mid for mid, (_, _, producer, _) in msgs.items() if producer == "pos"}
    assert pos and all(mid in dead_after for mid in pos) and not pos & (all_fixed | single)
    print(f"pos refunds dead-lettered and counted for no defect: {len(pos)}")

    by_reason_guess = {"retry-budget": reasons.get("attempts-exhausted", 0), "idempotency": reasons.get("key-conflict", 0),
                       "visibility": reasons.get("lease-lost", 0), "schema": reasons.get("schema-rejected", 0)}
    print("counts by logged reason (a shortcut):", by_reason_guess)

    poisoned = {}
    for b in bugs.SHIPPED:
        got = turned(app, work / f"fix-{b}", world.stamp(poison_start))
        poisoned[b] = (len(got), got[0][1])
        mine = next(c for c in truth["causes"] if c["id"] == b)
        assert poisoned[b] != (mine["messages"], mine["first"]), b
    print("with the deploy at", world.stamp(poison_start), "the counts would be", poisoned)
    whole = {}
    for b in bugs.SHIPPED:
        got = turned(app, work / f"fix-{b}", world.stamp(starts[0]))
        whole[b] = (len(got), got[0][1])
    print("over the whole log, 4.1.3 included:", whole)

    hidden = tests / "hidden"
    if hidden.exists():
        shutil.rmtree(hidden)
    hroot = work / "hidden"
    (hroot / "config" / "history").mkdir(parents=True)
    for name, text in HIDDEN_CONFIGS.items():
        (hroot / "config" / "history" / f"{name}.toml").write_text(text, encoding="utf-8")
    hw = build.run_world(work / "hw", HIDDEN, (), (), HIDDEN["start"], HIDDEN_CONFIGS)
    build.write_logs(hroot, hw)
    copy_with_canary(hroot, hidden, skip=("worker.log", "checkpoints"))
    hres = hw["played"]["outcomes"]
    hreasons: dict[str, int] = {}
    for o in hres.values():
        hreasons[o[0]] = hreasons.get(o[0], 0) + 1
    print(f"hidden: {len(hw['drawn']['messages'])} messages, {dict(sorted(hreasons.items()))}")

    for d in ("ref", "visible", "runner"):
        if (tests / d).exists():
            shutil.rmtree(tests / d)
    copy_with_canary(HERE / "src" / "quayside", tests / "ref" / "quayside")
    copy_with_canary(HERE / "src" / "tests", tests / "visible")
    (tests / "runner").mkdir()
    (tests / "runner" / "replay.py").write_text(with_canary((HERE / "src" / "tools" / "replay.py").read_text(encoding="utf-8")), encoding="utf-8")
    (tests / "truth.json").write_text(json.dumps({"canary": CANARY.lstrip("# "), **truth}, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    hcheck = work / "hidden-check" / "root"
    shutil.copytree(hidden, hcheck)
    (hcheck / "tools").mkdir()
    shutil.copyfile(tests / "runner" / "replay.py", hcheck / "tools" / "replay.py")
    want = replay_tool(hcheck, HERE / "src", "--times")
    assert want[-1].endswith(" 0 differ from the log"), want[-1]
    for label, ids in [("shipped", bugs.SHIPPED)] + [(f"{b} alone", (b,)) for b in bugs.SHIPPED] + [(f"{b} fixed alone", tuple(x for x in bugs.SHIPPED if x != b)) for b in bugs.SHIPPED]:
        pkg = build.package_tree(work / "hv" / label.replace(" ", "-"), ids).parent
        got = replay_tool(hcheck, pkg, "--times")
        differ = sum(1 for a, b in zip(want, got) if a != b)
        assert differ > 0, label
        print(f"hidden replay, {label}: {differ} lines differ")
    return 0


if __name__ == "__main__":
    sys.exit(main())
