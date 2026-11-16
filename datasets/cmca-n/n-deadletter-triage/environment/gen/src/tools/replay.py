"""Replays the logged queue traffic through the quayside package (docs/operations.md 5).

    python3 tools/replay.py [--root DIR] [--pkg DIR] [--since TIME] [--until TIME] [--diff] [--times]

Reads ROOT/logs/service.log, ROOT/logs/queue/*.log, ROOT/logs/downstream.log,
ROOT/config/history and ROOT/var/checkpoints. Starts at the last `started`
line at or before --since with the checkpoint that line names (the first
`started` line without --since), and runs every enqueued message, reload,
stop and start in log order, with each downstream service answering as
downstream.log says it did. Prints one line per message with how the log
and the replay disposed of it; --diff prints only the messages where the
two differ, --times adds when the replay disposed of each message and after
how many deliveries. --pkg names a directory holding a `quayside` package to
use instead of the one next to tools/.
"""

import argparse
import bisect
import importlib
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
ENQUEUE = re.compile(r"^(\S+) enqueue (m[0-9]+) (\S+) producer=(\S+) (\{.*\})$")
DISPOSE = re.compile(r"^(\S+) (done|duplicate|dead-letter) (m[0-9]+)(?: of=m[0-9]+| reason=(\S+))?$")
SERVICE = re.compile(r"^(\S+) (started config=(r[0-9]+)(?: checkpoint=(\S+))?|stopping(?: checkpoint=\S+)?|config reload rev=([0-9]+)|stats .*)$")
DOWNSTREAM = re.compile(r"^(\S+) (\S+) state=(ok|down|throttled)(?: retry_after=([0-9]+)s)?$")
SERVICES = {"email.send": "mailer", "refund.issue": "payments", "invoice.render": "pdfgen", "stock.sync": "inventory"}
FIELDS = {
    "email.send": ("order", "to", "template"),
    "refund.issue": ("order", "amount", "card"),
    "invoice.render": ("order", "lines"),
    "stock.sync": ("order", "sku", "qty"),
}
KIND_ORDER = {"started": 0, "stopping": 0, "reload": 0, "enqueue": 1, "end": 2}


def to_ms(text: str) -> int:
    return (datetime.fromisoformat(text) - EPOCH) // timedelta(milliseconds=1)


def stamp(ms: int) -> str:
    t = EPOCH + timedelta(milliseconds=ms)
    return t.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ms % 1000:03d}Z"


def read_lines(path: Path):
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip() and not line.startswith("#"):
            yield number, line


class Downstream:
    """The state of each downstream service over time, from downstream.log."""

    def __init__(self, changes):
        self.times: dict[str, list[int]] = {}
        self.states: dict[str, list[tuple[str, int]]] = {}
        for at, svc, state, retry_after in sorted(changes, key=lambda c: (c[1], c[0])):
            self.times.setdefault(svc, []).append(at)
            self.states.setdefault(svc, []).append((state, retry_after))

    @classmethod
    def read(cls, path: Path) -> "Downstream":
        changes = []
        for number, line in read_lines(path):
            m = DOWNSTREAM.match(line)
            if not m:
                raise SystemExit(f"downstream.log:{number}: cannot read {line!r}")
            changes.append((to_ms(m.group(1)), m.group(2), m.group(3), int(m.group(4) or 0) * 1000))
        return cls(changes)

    def state(self, svc: str, at: int) -> tuple[str, int]:
        times = self.times.get(svc, [])
        i = bisect.bisect_right(times, at) - 1
        return self.states[svc][i] if i >= 0 else ("ok", 0)

    def attempt(self, m: dict, at: int) -> tuple[str, int, int, str]:
        """(outcome, milliseconds, retry_after in milliseconds, detail) of one handler run."""
        job, p = m["type"], m["payload"]
        jit = (int(m["id"][1:]) * 7919 + m["receives"] * 104729) % 1000
        svc = SERVICES[job]
        if not isinstance(p, dict) or p.get("v") not in (2, 3) or any(f not in p for f in FIELDS[job]):
            return ("rejected", 30 + jit % 20, 0, f"{svc}: 400 Bad Request")
        state, retry_after = self.state(svc, at)
        if state == "down":
            return ("error", 5000, 0, f"{svc}: 503 Service Unavailable")
        if state == "throttled":
            return ("throttled", 40 + jit % 10, retry_after, f"{svc}: 429 Too Many Requests")
        if job == "refund.issue" and p["card"] == "expired":
            return ("rejected", 700 + jit % 100, 0, "payments: 402 card expired")
        if job == "email.send":
            ms = 250 + jit % 300
        elif job == "refund.issue":
            ms = 900 + jit // 2
        elif job == "invoice.render":
            lines = p["lines"] if isinstance(p["lines"], list) else [p["lines"]]
            ms = 3000 + 9000 * len(lines) + jit
        else:
            ms = 400 + jit // 3
        return ("ok", ms, 0, "")


def make_items(services, enqueues, end: int) -> list[tuple]:
    """(ms, order, n, kind, fields) in log order; services and enqueues as read from the logs."""
    items = []
    for n, (at, kind, fields) in enumerate(services):
        items.append((at, KIND_ORDER[kind], n, kind, fields))
    for n, (at, fields) in enumerate(enqueues):
        items.append((at, KIND_ORDER["enqueue"], n, "enqueue", fields))
    items.append((end, KIND_ORDER["end"], 0, "end", {}))
    return sorted(items, key=lambda it: it[:3])


def read_root(root: Path) -> dict:
    services, enqueues, logged = [], [], {}
    end = None
    for number, line in read_lines(root / "logs" / "service.log"):
        m = SERVICE.match(line)
        if not m:
            raise SystemExit(f"service.log:{number}: cannot read {line!r}")
        at, what = to_ms(m.group(1)), m.group(2)
        end = at
        if what.startswith("started"):
            services.append((at, "started", {"config": m.group(3), "checkpoint": m.group(4)}))
        elif what.startswith("stopping"):
            services.append((at, "stopping", {}))
        elif what.startswith("config reload"):
            services.append((at, "reload", {"config": f"r{int(m.group(5)):03d}"}))
    for log in sorted((root / "logs" / "queue").glob("*.log")):
        for number, line in read_lines(log):
            m = ENQUEUE.match(line)
            if m:
                enqueues.append((to_ms(m.group(1)), {"id": m.group(2), "type": m.group(3), "payload": json.loads(m.group(5))}))
                continue
            m = DISPOSE.match(line)
            if not m:
                raise SystemExit(f"{log.name}:{number}: cannot read {line!r}")
            what = m.group(2) if m.group(2) != "dead-letter" else f"dead-letter:{m.group(4)}"
            logged[m.group(3)] = (what, to_ms(m.group(1)))
    configs = {p.stem: p.read_text(encoding="utf-8") for p in sorted((root / "config" / "history").glob("r*.toml"))}
    return {
        "items": make_items(services, enqueues, end),
        "logged": logged,
        "configs": configs,
        "env": Downstream.read(root / "logs" / "downstream.log"),
    }


def play(items, release, configs, env, start: int = 0, state=None, until=None, marks=(), on_mark=None) -> dict:
    """Runs items from index start. release(ms) gives the package a `started` line runs.

    Returns the outcome of every message disposed of, the engine logs, the
    checkpoint written at each stop, and the ids of the messages the run saw."""
    out = {"outcomes": {}, "log": [], "checkpoints": {}, "seen": set()}
    marks = sorted(marks)
    mi = 0
    eng = None

    def close():
        out["outcomes"].update(eng.outcomes)
        out["log"].extend(eng.log)

    for at, _, _, kind, fields in items[start:]:
        if until is not None and at > until:
            break
        while mi < len(marks) and marks[mi] <= at:
            if eng is not None:
                eng.advance(marks[mi])
            on_mark(marks[mi], eng, state)
            mi += 1
        if eng is not None:
            eng.advance(at)
        if kind == "started":
            pkg = release(at)
            eng = pkg.broker.Engine(pkg.config.parse(configs[fields["config"]]), env, state, at)
            if state is not None:
                out["seen"].update(m["id"] for m in state["messages"])
        elif kind == "stopping":
            state = json.loads(json.dumps(eng.stop(at)))
            out["checkpoints"][at] = state
            close()
            eng = None
        elif kind == "reload":
            if eng is not None:
                eng.reload(pkg.config.parse(configs[fields["config"]]))
        elif kind == "enqueue":
            if eng is None:
                raise SystemExit(f"{fields['id']}: enqueued while the queue is stopped")
            eng.enqueue(fields["id"], fields["type"], fields["payload"], at)
            out["seen"].add(fields["id"])
    if eng is not None:
        if until is not None:
            eng.advance(until + 1)
        close()
    return out


def load_package(pkg_dir: Path):
    sys.path.insert(0, str(pkg_dir.resolve()))
    importlib.import_module("quayside.config")
    importlib.import_module("quayside.broker")
    return importlib.import_module("quayside")


def replay(root: Path, pkg_dir: Path, since: str | None, until: str | None, diff: bool, times: bool, out=sys.stdout) -> int:
    pkg = load_package(pkg_dir)
    world = read_root(root)
    items = world["items"]
    since_ms = to_ms(since) if since else None
    until_ms = to_ms(until) if until else None
    starts = [i for i, it in enumerate(items) if it[3] == "started" and (since_ms is None or it[0] <= since_ms)]
    if not starts:
        raise SystemExit("no started line at or before --since")
    first = starts[-1] if since_ms is not None else starts[0]
    state = None
    if items[first][4]["checkpoint"]:
        state = json.loads((root / items[first][4]["checkpoint"]).read_text(encoding="utf-8"))
    got = play(items, lambda at: pkg, world["configs"], world["env"], first, state, until_ms)
    counts = {"done": 0, "duplicate": 0, "dead-letter": 0, "pending": 0}
    differ = 0
    for mid in sorted(got["seen"]):
        logged = world["logged"].get(mid)
        if logged is not None and until_ms is not None and logged[1] > until_ms:
            logged = None
        if logged is not None and since_ms is not None and logged[1] < since_ms:
            continue
        mine = got["outcomes"].get(mid)
        left = f"{logged[0]}@{stamp(logged[1])}" if logged else "pending"
        right = mine[0] if mine else "pending"
        counts[right.split(":")[0]] += 1
        same = right == (logged[0] if logged else "pending")
        differ += not same
        if diff and same:
            continue
        if times and mine:
            right += f"@{stamp(mine[1])}#{mine[2]}"
        print(f"{mid} logged={left} replay={right}", file=out)
    total = sum(counts.values())
    print(f"# {total} messages replayed: {counts['done']} done, {counts['duplicate']} duplicate, {counts['dead-letter']} dead-letter, {counts['pending']} pending; {differ} differ from the log", file=out)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    ap.add_argument("--pkg", type=Path, default=Path(__file__).resolve().parent.parent)
    ap.add_argument("--since")
    ap.add_argument("--until")
    ap.add_argument("--diff", action="store_true")
    ap.add_argument("--times", action="store_true")
    args = ap.parse_args(argv)
    return replay(args.root, args.pkg, args.since, args.until, args.diff, args.times)


if __name__ == "__main__":
    sys.exit(main())
