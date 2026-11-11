"""Authoring only, not run by the image build.

    python3 plan.py TASK_DIR

Builds the public tree as the image does, writes tests/truth.json (for every
shipped defect, the logged misses of 2.4.0 requests that become hits when
that defect alone is fixed, and the first of them), draws the verifier's
held-out traffic into tests/hidden, and copies the reference package, the
visible tests and the replay tool into tests/ with the canary on top. It
stops if the history does not have the properties the walkthrough states,
and prints the numbers the walkthrough quotes.
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
POISON_DEPLOY = "2027-05-03T11:00:03+00:00"

HIDDEN_LANGS = [
    ("en-US,en;q=0.9", 20), ("en-GB,en;q=0.8", 10), ("en-AU", 5), ("EN-gb", 2), ("es-419,es;q=0.9", 6), ("es", 4),
    ("pt-PT,pt;q=0.8", 4), ("pt-BR", 4), ("ja-JP,ja;q=0.9,en;q=0.5", 5), ("fr-FR,fr;q=0.9", 4), ("de;q=0, es;q=0.5", 2),
    ("*", 2), ("-", 3),
]

HIDDEN = {
    "seed": 90731,
    "first_id": 500001,
    "start": "2027-08-16T06:00:00+00:00",
    "end": "2027-08-16T18:00:00+00:00",
    "books": 900, "book_heads": (10, 90, 16), "popular_books": 240, "authors": 200, "popular_authors": 60, "queries": 30,
    "rate_day": 14, "rate_night": 6, "day": (8, 20),
    "langs": HIDDEN_LANGS,
    "click_param": "gclid",
    "purge_every": 4, "author_purge_every": 20,
    "stops": [("2027-08-16T12:00:00+00:00", "2027-08-16T12:00:04+00:00")],
    "campaign": {"from": "2027-08-16T09:00:00+00:00", "chance": (25, 100), "burst_min": 60, "burst_rate": 5},
    "extra_params": [
        {"name": "utm_id", "from": "2027-08-16T06:00:00+00:00", "routes": ["books", "search"], "chance": (8, 100), "values": ["a17", "b22", "c35"]},
        {"name": "referrer", "from": "2027-08-16T06:00:00+00:00", "routes": ["books", "search"], "chance": (4, 100), "values": ["mail", "feed"]},
        {"name": "UTM_Source", "from": "2027-08-16T06:00:00+00:00", "routes": ["books"], "chance": (3, 100), "values": ["Feed"]},
    ],
    "events": [
        ("2027-08-16T06:00:00+00:00", "started config=r101"),
        ("2027-08-16T08:00:00+00:00", "config reload rev=102"),
        ("2027-08-16T10:30:00+00:00", "cache flush"),
        ("2027-08-16T12:00:00+00:00", "stopping"),
        ("2027-08-16T12:00:04+00:00", "started config=r102"),
        ("2027-08-16T15:00:00+00:00", "config reload rev=103"),
    ],
}

HIDDEN_CONFIGS = {
    "r101": """rev = 101
locales = ["en", "en-GB", "es", "pt-BR", "ja"]
default_locale = "en"
ignore_params = ["ref", "gclid", "utm_source"]

[routes.books]
ttl = 1800
vary = ["Accept-Language"]

[routes.authors]
ttl = "2h"
vary = []

[routes.search]
ttl = 120
vary = ["Accept-Language"]
""",
    "r102": """rev = 102
locales = ["en", "en-GB", "es", "pt-BR", "ja"]
default_locale = "en"
ignore_params = ["utm_source", "gclid", "ref"]

[routes.search]
ttl = "90s"
vary = ["Accept-Language"]

[routes.books]
ttl = "45m"
vary = ["Accept-Language"]

[routes.authors]
ttl = 5400
vary = ["Accept-Language"]
""",
    "r103": """rev = 103
locales = ["en", "en-GB", "es", "pt-BR", "ja"]
default_locale = "en"
ignore_params = ["utm_source", "gclid", "ref"]

[routes.search]
ttl = "1500ms"
vary = ["Accept-Language"]

[routes.books]
ttl = 900
vary = ["Accept-Language"]

[routes.authors]
ttl = "3h"
vary = ["Accept-Language"]
""",
}


def with_canary(text: str, mark: str = "#") -> str:
    return f"{mark} {CANARY.lstrip('# ')}\n{text}"


def copy_with_canary(src: Path, dst: Path) -> None:
    for p in sorted(src.rglob("*")):
        if "__pycache__" in p.parts or p.is_dir():
            continue
        out = dst / p.relative_to(src)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(with_canary(p.read_text(encoding="utf-8")), encoding="utf-8")


def replay_tool(root: Path, pkg_parent: Path, *args: str) -> list[str]:
    r = subprocess.run([sys.executable, "-B", str(root / "tools" / "replay.py"), "--root", str(root), "--pkg", str(pkg_parent), *args],
                       capture_output=True, text=True, check=True)
    return r.stdout.splitlines()


def count_fixed(w: dict, pkg, start_at: int, from_ms: int) -> list[str]:
    """Logged misses at or after from_ms that are hits when pkg serves from the started line at start_at."""
    tl = w["timeline"]
    start = [i for i, it in enumerate(tl) if it[2] == "started" and it[0] == start_at][0]
    got = build.play(tl, lambda at: pkg, w["configs"], start=start)["results"]
    logged = w["played"]["results"]
    return [it[3]["id"] for it in tl[start:] if it[2] == "request" and it[0] >= from_ms and logged[it[3]["id"]] == "miss" and got[it[3]["id"]] == "hit"]


def main() -> int:
    task = Path(sys.argv[1]).resolve()
    tests = task / "tests"
    work = Path(tempfile.mkdtemp())
    app = work / "app"
    subprocess.run([sys.executable, "-B", str(HERE / "build.py"), str(app)], check=True)
    w = build.run_world(work / "w")
    tl, logged = w["timeline"], w["played"]["results"]
    starts = [it[0] for it in tl if it[2] == "started"]
    deploy_start = min(t for t in starts if t >= w["cut"])
    poison_start = min(t for t in starts if t >= world.to_ms(POISON_DEPLOY))

    tail = replay_tool(app, app, "--since", world.stamp(deploy_start), "--diff")[-1]
    assert tail.endswith(" 0 differ from the log"), tail
    old_dir = build.package_tree(work / "old", bugs.OLD, build.OLD_VERSION).parent
    tail = replay_tool(app, old_dir, "--until", world.stamp(deploy_start - 1), "--diff")[-1]
    assert tail.endswith(" 0 differ from the log"), tail
    print("shipped replay from", world.stamp(deploy_start), "and 2.3.1 replay before it reproduce the log")

    variants = {}
    for b in bugs.SHIPPED:
        variants[b] = build.load_package(build.package_tree(work / f"fix-{b}", [x for x in bugs.SHIPPED if x != b]), f"plan_fix_{b}")
    correct = build.load_package(build.package_tree(work / "correct", ()), "plan_correct")
    truth = {"causes": []}
    found = {}
    for b in bugs.SHIPPED:
        ids = count_fixed(w, variants[b], deploy_start, deploy_start)
        found[b] = set(ids)
        bug = next(x for x in bugs.BUGS if x[0] == b)
        lines = bugs.accepted_lines(app / "shelfmark", b)
        truth["causes"].append({"id": b, "class": bug[1], "file": f"shelfmark/{bug[2]}", "lines": lines, "requests": len(ids), "first": ids[0]})
        assert len(ids) >= 10, (b, len(ids))
    all_fixed = set(count_fixed(w, correct, deploy_start, deploy_start))
    single = set().union(*found.values())
    two = all_fixed - single
    assert len(two) >= 50, len(two)
    req = {it[3]["id"]: it for it in tl if it[2] == "request"}
    served = [it for it in tl if it[2] == "request" and it[0] >= deploy_start]
    misses = sum(1 for it in served if logged[it[3]["id"]] == "miss")
    print(f"2.4.0 requests {len(served)}, logged misses {misses}, hits with every defect fixed {len(all_fixed)}, with one fixed {len(single)}, needing two or more fixes {len(two)}, hits with one fixed but not with all {len(single - all_fixed)}")
    for c in truth["causes"]:
        print(f"{c['id']} {c['class']} {c['file']}:{c['lines']} requests={c['requests']} first={c['first']} at {world.stamp(req[c['first']][0])}")

    reload43 = world.to_ms("2027-05-03T20:00:00+00:00")
    b3_first = req[truth["causes"][2]["first"]][0]
    assert b3_first > reload43, "B3 shows only after rev 43"
    campaign = world.to_ms(world.PUBLIC["campaign"]["from"])
    b2 = sorted(req[i][0] for i in found["B2"])
    assert b2[0] < campaign and sum(1 for t in b2 if t >= campaign) > 2 * sum(1 for t in b2 if t < campaign), "B2: partner trickle first, campaign most"
    print(f"B2 before the campaign {sum(1 for t in b2 if t < campaign)}, after {sum(1 for t in b2 if t >= campaign)}")

    poisoned = {}
    for b in bugs.SHIPPED:
        ids = count_fixed(w, variants[b], poison_start, poison_start)
        poisoned[b] = (len(ids), ids[0])
        mine = next(c for c in truth["causes"] if c["id"] == b)
        assert (len(ids), ids[0]) != (mine["requests"], mine["first"]), b
    print("with the deploy at", world.stamp(poison_start), "the counts would be", poisoned)

    flush_at = world.to_ms("2027-05-04T09:20:00+00:00")
    after_flush = [it for it in served if flush_at <= it[0] < flush_at + 600_000 and logged[it[3]["id"]] == "miss"]
    purge_self = 0
    purged: dict[str, int] = {}
    for it in served:
        r = it[3]
        if r["method"] == "PURGE":
            purged[r["target"]] = it[0]
        elif logged[r["id"]] == "miss" and r["target"].split("?")[0] in purged and it[0] - purged[r["target"].split("?")[0]] < 600_000:
            purge_self += 1
    incident = [world.to_ms(t) for t in world.PUBLIC["incident"]]
    slow = [it for it in served if incident[0] <= it[0] < incident[1]]
    assert after_flush and purge_self and slow
    print(f"misses in the 10 minutes after the flush {len(after_flush)}; misses of a purged id within 10 minutes of its purge {purge_self}; requests during the upstream incident {len(slow)}")

    hidden = tests / "hidden"
    if hidden.exists():
        shutil.rmtree(hidden)
    hroot = work / "hidden"
    (hroot / "config" / "history").mkdir(parents=True)
    for name, text in HIDDEN_CONFIGS.items():
        (hroot / "config" / "history" / f"{name}.toml").write_text(text, encoding="utf-8")
    hw = build.run_world(work / "hw", HIDDEN, (), (), HIDDEN["start"], HIDDEN_CONFIGS)
    build.write_logs(hroot, hw)
    copy_with_canary(hroot, hidden)
    hres = hw["played"]["results"]
    print(f"hidden: {len(hres)} requests, {sum(1 for v in hres.values() if v == 'hit')} hits, {sum(1 for v in hres.values() if v == 'miss')} misses")

    for d in ("ref", "visible", "runner"):
        if (tests / d).exists():
            shutil.rmtree(tests / d)
    copy_with_canary(HERE / "src" / "shelfmark", tests / "ref" / "shelfmark")
    copy_with_canary(HERE / "src" / "tests", tests / "visible")
    (tests / "runner").mkdir()
    (tests / "runner" / "replay.py").write_text(with_canary((HERE / "src" / "tools" / "replay.py").read_text(encoding="utf-8")), encoding="utf-8")
    (tests / "truth.json").write_text(json.dumps({"canary": CANARY.lstrip("# "), **truth}, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    hroot_t = work / "hidden-check"
    shutil.copytree(hidden, hroot_t / "root")
    (hroot_t / "root" / "tools").mkdir()
    shutil.copyfile(tests / "runner" / "replay.py", hroot_t / "root" / "tools" / "replay.py")
    want = replay_tool(hroot_t / "root", HERE / "src")
    assert want[-1].endswith(" 0 differ from the log"), want[-1]
    for label, ids in [("shipped", bugs.SHIPPED)] + [(f"{b} alone", (b,)) for b in bugs.SHIPPED] + [(f"{b} fixed alone", tuple(x for x in bugs.SHIPPED if x != b)) for b in bugs.SHIPPED]:
        pkg = build.package_tree(work / "hv" / label.replace(" ", "-"), ids).parent
        got = replay_tool(hroot_t / "root", pkg)
        differ = sum(1 for a, b in zip(want, got) if a != b)
        assert differ > 0, label
        print(f"hidden replay, {label}: {differ} lines differ")
    return 0


if __name__ == "__main__":
    sys.exit(main())
