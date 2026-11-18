"""Authoring only, not run by the image build.

    python3 plan.py TASK_DIR

Draws the public schedule (gen/schedule.json) and the verifier's held-out
schedule (tests/hidden_schedule.json), runs the public one the way build.py
does, and writes tests/truth.json: for every shipped defect, the snapshots of
4.2.0 runs whose state changes when that defect alone is fixed (for B4, when
the run is retried from the state written just before its own). It stops if
the schedule does not have the properties the walkthrough states.
"""

import copy
import json
import random
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import build  # noqa: E402
import bugs  # noqa: E402

UTC = timezone.utc


def ts(t: datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def st(t: datetime) -> str:
    return t.astimezone(UTC).strftime("%Y%m%dT%H%M")


def at(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def lisbon(t: datetime, rng=None) -> str:
    """Local time of the city: WET until 2027-03-28T01:00Z, WEST after."""
    offset = timedelta(hours=1) if t >= at("2027-03-28T01:00:00Z") else timedelta(0)
    local = (t + offset).replace(tzinfo=None)
    return local.strftime("%Y-%m-%dT%H:%M:%S") + ("+01:00" if offset else "+00:00")


HIDDEN_OFFSETS = [timedelta(hours=5, minutes=30), timedelta(hours=-3), timedelta(hours=1), timedelta(0), None, timedelta(hours=-7), timedelta(hours=9, minutes=45)]


def mixed(t: datetime, rng) -> str:
    offset = rng.choice(HIDDEN_OFFSETS)
    if offset is None:
        return ts(t)
    return t.astimezone(timezone(offset)).isoformat()


def header(batch: str, kind: str, count: int, delivered: str) -> str:
    return json.dumps({"batch": batch, "kind": kind, "count": count, "delivered": delivered}, sort_keys=True)


def feed_text(head: str, records: list[dict]) -> str:
    return "\n".join([head, *(json.dumps(r, sort_keys=True) for r in records)]) + "\n"


class World:
    """Draws a schedule slot by slot, keeping a running copy of the books to pick plausible docks."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.rng = random.Random(cfg["seed"])
        self.correct = build.load_package(build.package_tree(Path(tempfile.mkdtemp()), ()), f"plan_correct_{cfg['seed']}")
        self.runs: list[dict] = []
        self.feeds: dict[str, str] = {}
        self.trip_feeds: dict[str, tuple[str, str]] = {}
        self.hold_counter = cfg["first_hold"]
        self.trip_counter = cfg["first_trip"]

    def local(self, t: datetime) -> str:
        return self.cfg["local"](t, self.rng)

    def initial(self) -> dict:
        rng, cfg = self.rng, self.cfg
        docks = {}
        for i in range(cfg["docks"]):
            cap = rng.randint(20, 30)
            docks[f"D{i + 1:02d}"] = {"bikes": rng.randint(cap // 2 - 2, cap // 2 + 3), "capacity": cap}
        members = {}
        for i in range(cfg["members"]):
            members[f"M{1001 + i}"] = {"balance_cents": rng.randint(-3000, 2000), "plan": rng.choice(["monthly", "monthly", "monthly", "payg", "payg"]), "trips": rng.randint(0, 80)}
        applied = {}
        t = cfg["applied_from"]
        while t < cfg["start"]:
            applied[self.batch_id(t)] = ts(t)
            t += timedelta(minutes=15)
        meta = {"at": ts(cfg["start"] - timedelta(minutes=9, seconds=54)), "job": "holds", "rev": cfg["first_rev"], "version": cfg["first_version"]}
        self.state = {"docks": docks, "members": members, "holds": {}, "applied": applied, "meta": meta}
        return copy.deepcopy(self.state)

    def batch_id(self, t: datetime) -> str:
        slot = int((t - self.cfg["epoch"]).total_seconds() // 900)
        return f"T{self.cfg['first_batch'] + slot:06d}"

    def add(self, run: dict, feed: str | None = None, text: str | None = None) -> None:
        if feed:
            run["feed"] = feed
            self.feeds[feed] = text
        self.runs.append(run)

    def apply_books(self, job: str, batch) -> None:
        now = at(self.runs[-1]["start"])
        self.state = self.correct.jobs.JOBS[job].run(self.state, batch, now)

    def trips(self, t: datetime, redeliver: str | None, broken: bool, resend: str | None) -> None:
        rng = self.rng
        rid = f"t-{st(t)}"
        dur = rng.randint(4, 25)
        run = {"id": rid, "job": "trips", "start": ts(t), "end": ts(t + timedelta(seconds=dur))}
        if redeliver or resend:
            old_t = at(redeliver or resend)
            batch, text = self.trip_feeds[self.batch_id(old_t)]
            self.add(run, f"feeds/trips/{st(t)}-{batch}.jsonl", text)
            self.apply_books("trips", self.parse(text))
            return
        records = []
        docks = self.state["docks"]
        for _ in range(rng.choice([0, 1, 1, 2, 2, 3, 3, 4, 5])):
            sources = [d for d, v in sorted(docks.items()) if v["bikes"] >= 4]
            targets = [d for d, v in sorted(docks.items()) if v["capacity"] - v["bikes"] >= 4]
            if not sources or not targets:
                continue
            src, dst = rng.choice(sources), rng.choice(targets)
            member = rng.choice(sorted(self.state["members"]))
            if rng.random() < 0.15:
                seconds = 60 * rng.randint(3, 70)
            elif rng.random() < 0.3:
                seconds = rng.randint(1800, 4200)
            else:
                seconds = rng.randint(100, 1790)
            end = t - timedelta(seconds=rng.randint(5, 880))
            start = end - timedelta(seconds=seconds)
            self.trip_counter += 1
            records.append({"trip": f"R{self.trip_counter}", "member": member, "from": src, "to": dst, "start": self.local(start), "end": self.local(end)})
        records.sort(key=lambda r: (at(r["end"]), r["trip"]))
        batch = self.batch_id(t)
        text = feed_text(header(batch, "trips", len(records), self.local(t - timedelta(seconds=rng.randint(10, 50)))), records)
        self.trip_feeds[batch] = (batch, text)
        if broken:
            lines = text.splitlines()
            cut = lines[-1][: len(lines[-1]) // 2]
            bad = "\n".join(lines[:-1] + [cut]) + "\n"
            self.add(run, f"feeds/trips/{st(t)}-{batch}.jsonl", bad)
            return
        self.add(run, f"feeds/trips/{st(t)}-{batch}.jsonl", text)
        self.apply_books("trips", self.parse(text))

    def parse(self, text: str) -> dict:
        lines = text.splitlines()
        head = json.loads(lines[0])
        return {"batch": head["batch"], "kind": head["kind"], "records": [json.loads(x) for x in lines[1:] if x.strip()]}

    def holds(self, t: datetime, mode: str, dur: int | None) -> None:
        rng = self.rng
        dur = dur or rng.randint(2, 9)
        run = {"id": f"h-{st(t)}", "job": "holds", "start": ts(t), "end": ts(t + timedelta(seconds=dur))}
        if mode == "force":
            n = 1 + (rng.random() < 0.3)
        elif mode == "quiet":
            n = 0
        else:
            n = 1 if rng.random() < self.cfg["hold_rate"] else 0
        records = []
        for _ in range(n):
            docks = [d for d, v in sorted(self.state["docks"].items()) if v["bikes"] >= 3]
            self.hold_counter += 1
            until = t + timedelta(minutes=rng.randint(15, 50), seconds=rng.choice([0, 0, rng.randint(1, 59)]))
            records.append({"hold": f"H{self.hold_counter}", "member": rng.choice(sorted(self.state["members"])), "dock": rng.choice(docks), "until": self.local(until)})
        batch = f"H{st(t)}"
        text = feed_text(header(batch, "holds", len(records), self.local(t - timedelta(seconds=rng.randint(5, 40)))), records)
        self.add(run, f"feeds/holds/{st(t)}-{batch}.jsonl", text)
        self.apply_books("holds", self.parse(text))

    def rebalance(self, t: datetime, dur: int | None, empty: bool) -> None:
        rng = self.rng
        dur = dur or rng.randint(40, 100)
        run = {"id": f"r-{st(t)}", "job": "rebalance", "start": ts(t), "end": ts(t + timedelta(seconds=dur))}
        records = []
        if not empty:
            docks = self.state["docks"]
            by_fill = sorted(docks, key=lambda d: (docks[d]["bikes"] / docks[d]["capacity"], d))
            for src, dst in ((by_fill[-1], by_fill[0]), (by_fill[-2], by_fill[1]))[: rng.randint(1, 2)]:
                room = docks[dst]["capacity"] - docks[dst]["bikes"]
                n = max(2, min(6, (docks[src]["bikes"] - docks[dst]["bikes"]) // 2, room))
                records.append({"from": src, "to": dst, "bikes": n})
        batch = f"M{st(t)}"
        text = feed_text(header(batch, "rebalance", len(records), self.local(t - timedelta(minutes=rng.randint(20, 50)))), records)
        self.add(run, f"feeds/rebalance/{st(t)}-{batch}.jsonl", text)
        self.apply_books("rebalance", self.parse(text))

    def compact(self, t: datetime) -> None:
        run = {"id": f"c-{st(t)}", "job": "compact", "start": ts(t), "end": ts(t + timedelta(seconds=self.rng.randint(1, 3)))}
        self.add(run)
        self.apply_books("compact", None)

    def draw(self) -> dict:
        cfg = self.cfg
        initial = self.initial()
        overlaps = {at(k): v for k, v in cfg["overlaps"].items()}
        quiet = [(at(a), at(b)) for a, b in cfg["quiet"]]
        redeliver = {at(k): v for k, v in cfg["redeliver"].items()}
        broken = at(cfg["broken"]) if cfg.get("broken") else None
        resend = broken + timedelta(minutes=15) if broken else None
        t = cfg["start"]
        pending_hold_dur = None
        while t < cfg["end"]:
            m = t.minute
            if t == resend:
                self.trips(t, None, False, ts(broken))
            elif m % 15 == 0:
                self.trips(t, redeliver.get(t), t == broken, None)
            if m % 15 == 5:
                spec = overlaps.get(t - timedelta(minutes=2))
                in_quiet = any(a <= t <= b for a, b in quiet)
                mode = "quiet" if in_quiet else (spec["holds"] if spec else "random")
                self.holds(t, mode, pending_hold_dur)
                pending_hold_dur = None
            if m == 3 and t.hour % 3 == 0:
                spec = overlaps.get(t, {})
                self.rebalance(t, spec.get("rebalance"), spec.get("empty", False))
                pending_hold_dur = spec.get("holds_dur")
            if m == 32 and t.hour == 3:
                self.compact(t)
            if cfg.get("admin") and t == at(cfg["admin"]["start"]) - timedelta(seconds=at(cfg["admin"]["start"]).second):
                a = dict(cfg["admin"])
                a["end"] = a["start"]
                self.runs.append(a)
            t += timedelta(minutes=1)
        return {"initial": initial, "runs": self.runs, "feeds": self.feeds}


def public_cfg() -> dict:
    return {
        "seed": 5521,
        "local": lambda t, rng: lisbon(t),
        "epoch": at("2027-03-26T00:00:00Z"),
        "first_batch": 20001,
        "first_trip": 880400,
        "first_hold": 61200,
        "first_rev": 4120,
        "first_version": "4.1.2",
        "docks": 8,
        "members": 32,
        "hold_rate": 0.25,
        "start": at("2027-03-27T00:00:00Z"),
        "end": at("2027-03-29T12:00:00Z"),
        "applied_from": at("2027-03-26T01:30:00Z"),
        "overlaps": {
            "2027-03-27T06:03:00Z": {"rebalance": 200, "holds": "force"},
            "2027-03-27T18:03:00Z": {"rebalance": 190, "holds": "force"},
            "2027-03-27T21:03:00Z": {"rebalance": 122, "holds_dur": 7, "holds": "random"},
            "2027-03-28T06:03:00Z": {"rebalance": 175, "holds": "quiet"},
            "2027-03-28T15:03:00Z": {"rebalance": 205, "holds": "force"},
            "2027-03-29T03:03:00Z": {"rebalance": 123, "holds_dur": 6, "empty": True, "holds": "force"},
            "2027-03-29T09:03:00Z": {"rebalance": 121, "holds_dur": 8, "holds": "random"},
        },
        "quiet": [("2027-03-28T03:35:00Z", "2027-03-28T06:05:00Z")],
        "redeliver": {
            "2027-03-27T07:30:00Z": "2027-03-27T00:45:00Z",
            "2027-03-27T20:30:00Z": "2027-03-27T09:00:00Z",
            "2027-03-28T05:15:00Z": "2027-03-27T16:45:00Z",
            "2027-03-28T13:45:00Z": "2027-03-28T02:30:00Z",
            "2027-03-28T22:15:00Z": "2027-03-28T04:00:00Z",
            "2027-03-29T04:30:00Z": "2027-03-28T19:15:00Z",
            "2027-03-29T08:45:00Z": "2027-03-29T02:00:00Z",
            "2027-03-29T10:00:00Z": "2027-03-28T11:30:00Z",
        },
        "broken": "2027-03-28T10:15:00Z",
        "admin": {"id": "a-20270328T1120", "job": "admin", "start": "2027-03-28T11:20:07Z", "path": "members.M1012.balance_cents", "add": 500, "ticket": "OPS-2291", "by": "duty-ops"},
    }


def hidden_cfg() -> dict:
    return {
        "seed": 90417,
        "local": mixed,
        "epoch": at("2027-10-29T00:00:00Z"),
        "first_batch": 71001,
        "first_trip": 5100,
        "first_hold": 900,
        "first_rev": 100,
        "first_version": "4.2.0",
        "docks": 6,
        "members": 20,
        "hold_rate": 0.55,
        "start": at("2027-10-30T20:00:00Z"),
        "end": at("2027-10-31T23:00:00Z"),
        "applied_from": at("2027-10-28T12:00:00Z"),
        "overlaps": {
            "2027-10-30T21:03:00Z": {"rebalance": 150, "holds": "force"},
            "2027-10-31T00:03:00Z": {"rebalance": 122, "holds_dur": 8, "holds": "random"},
            "2027-10-31T06:03:00Z": {"rebalance": 200, "holds": "force"},
            "2027-10-31T09:03:00Z": {"rebalance": 123, "holds_dur": 9, "holds": "force"},
            "2027-10-31T15:03:00Z": {"rebalance": 180, "holds": "force"},
            "2027-10-31T18:03:00Z": {"rebalance": 121, "holds_dur": 9, "holds": "random"},
        },
        "quiet": [],
        "redeliver": {
            "2027-10-31T02:00:00Z": "2027-10-30T20:30:00Z",
            "2027-10-31T08:15:00Z": "2027-10-30T23:45:00Z",
            "2027-10-31T12:30:00Z": "2027-10-31T01:00:00Z",
            "2027-10-31T19:45:00Z": "2027-10-30T21:15:00Z",
            "2027-10-31T22:00:00Z": "2027-10-31T10:30:00Z",
        },
        "broken": "2027-10-31T05:30:00Z",
        "admin": None,
    }


def main() -> int:
    task = Path(sys.argv[1])
    canary = (task.parent.parent / "CANARY").read_text(encoding="utf-8").lstrip("# ").strip()
    public = World(public_cfg()).draw()
    public["deploy"] = {
        "at": "2027-03-27T14:10:00Z",
        "log": [
            "2027-03-11T10:02:51Z deploy spokehouse 4.1.0 change CHG-5893 by release-bot",
            "2027-03-19T09:12:40Z deploy spokehouse 4.1.1 change CHG-5980 by release-bot",
            "2027-03-24T16:02:11Z deploy spokehouse 4.1.2 change CHG-6034 by release-bot",
            "2027-03-27T14:08:30Z scheduler paused for deploy change CHG-6102",
            "2027-03-27T14:10:00Z deploy spokehouse 4.2.0 change CHG-6102 by release-bot",
            "2027-03-27T14:10:04Z scheduler resumed change CHG-6102",
        ],
    }
    public["ops_header"] = []
    public["audits"] = ["2027-03-28T00:00:00Z", "2027-03-29T00:00:00Z", "2027-03-29T12:00:00Z"]
    (HERE / "schedule.json").write_text(json.dumps(public, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    hidden = World(hidden_cfg()).draw()
    hidden["note"] = canary
    (task / "tests" / "hidden_schedule.json").write_text(json.dumps(hidden, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    with tempfile.TemporaryDirectory() as tmp:
        truth = analyze(Path(tmp))
    truth["note"] = canary
    (task / "tests" / "truth.json").write_text(json.dumps(truth, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return 0


def analyze(work: Path) -> dict:
    world = build.run_world(work)
    plan = world["plan"]
    hist = build.history(world["app"])
    names = [s["name"] for s in hist]
    if len(set(s["state"]["meta"]["at"] for s in hist)) != len(hist):
        raise SystemExit("two snapshots share a write time")
    by_name = {s["name"]: s["state"] for s in hist}
    prev = {names[i]: names[i - 1] for i in range(1, len(names))}
    runs = {r["id"]: r for r in plan["runs"]}

    variants = {"all": build.load_package(build.package_tree(work / "v-all", bugs.SHIPPED), "an_all"),
                "correct": build.load_package(build.package_tree(work / "v-correct", ()), "an_correct")}
    for b in bugs.SHIPPED:
        rest = tuple(x for x in bugs.SHIPPED if x != b)
        variants[f"minus-{b}"] = build.load_package(build.package_tree(work / f"v-minus-{b}", rest), f"an_minus_{b}")
        variants[f"only-{b}"] = build.load_package(build.package_tree(work / f"v-only-{b}", (b,)), f"an_only_{b}")
    sched = build.sched_module()

    def replay(pkg, run, state):
        feed = world["app"] / run["feed"] if run.get("feed") else None
        return pkg.store.data(sched.run_job(pkg, run["job"], state, feed, at(run["start"])))

    starts, ends = {}, {}
    for channel, line in world["lines"]:
        if channel != "sched":
            continue
        parts = line.split()
        fields = dict(p.split("=", 1) for p in parts[3:] if "=" in p)
        if parts[1] == "start":
            starts[fields["run"]] = fields
        elif parts[1] == "end":
            ends[fields["run"]] = fields
    causes = {b: [] for b in bugs.SHIPPED}
    stats = {"post_runs": 0, "wrong": 0, "pre_wrong": 0, "overlaps": 0, "harmless_overlaps": 0, "failed": 0}
    for rid, end in ends.items():
        if end["exit"] != "0":
            stats["failed"] += 1
            continue
        run, start = runs[rid], starts[rid]
        name = end["wrote"]
        actual = {k: by_name[name][k] for k in ("docks", "members", "holds", "applied")}
        loaded = by_name[start["loaded"]]
        before = by_name[prev[name]]
        if start["version"] != build.VERSION:
            if replay(variants["correct"], run, before) != actual:
                stats["pre_wrong"] += 1
            continue
        stats["post_runs"] += 1
        if replay(variants["all"], run, loaded) != actual:
            raise SystemExit(f"{rid}: replay with the shipped code does not reproduce {name}")
        if prev[name] != start["loaded"]:
            stats["overlaps"] += 1
        hit = []
        for b in bugs.SHIPPED:
            if b == "B4":
                changed = replay(variants["all"], run, before) != actual
                alone = prev[name] != start["loaded"] and replay(variants["only-B4"], run, loaded) != replay(variants["only-B4"], run, before)
            else:
                changed = replay(variants[f"minus-{b}"], run, loaded) != actual
                alone = replay(variants[f"only-{b}"], run, loaded) != replay(variants["correct"], run, loaded)
            if changed != alone:
                raise SystemExit(f"{rid}: {b}: fixing it alone and adding it alone disagree")
            if changed:
                hit.append(b)
                causes[b].append(name)
        if prev[name] != start["loaded"] and "B4" not in hit:
            stats["harmless_overlaps"] += 1
        wrong = replay(variants["correct"], run, before) != actual
        if wrong != bool(hit):
            raise SystemExit(f"{rid}: wrong={wrong} but causes {hit}")
        stats["wrong"] += wrong
    with tempfile.TemporaryDirectory() as tmp:
        pkg = build.package_tree(Path(tmp), bugs.SHIPPED)
        lines = {b: bugs.accepted_lines(pkg, b) for b in bugs.SHIPPED}
    classes = {b: c for b, c, *_ in bugs.BUGS}
    files = {b: f"spokehouse/{rel}" for b, _, rel, *_ in bugs.BUGS}
    out = {"causes": [{"id": b, "class": classes[b], "file": files[b], "lines": lines[b], "snapshots": sorted(causes[b])} for b in bugs.SHIPPED],
           "stats": stats, "snapshot_count": len(hist)}
    for b in bugs.SHIPPED:
        print(b, len(causes[b]), causes[b][:6], file=sys.stderr)
    print(json.dumps(stats), file=sys.stderr)
    for b in bugs.SHIPPED:
        if len(causes[b]) < 2:
            raise SystemExit(f"{b}: only {len(causes[b])} snapshots")
    if stats["harmless_overlaps"] < 1 or stats["pre_wrong"] < 1 or stats["failed"] != 1:
        raise SystemExit(f"schedule lacks a decoy: {stats}")
    return out


if __name__ == "__main__":
    sys.exit(main())
