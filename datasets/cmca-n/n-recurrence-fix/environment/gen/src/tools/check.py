"""Consistency checks on the event documents the agenda package builds from a data directory.

Usage, from /app:

    python tools/check.py [--data DIR]

The tool expands every event in DIR (./data when left out) with the package
and checks properties that every correct document has: instances that last
their duration, local times that agree with their UTC times, instances in
time order and inside the window, one instance per recurrence id. It prints,
per rule, how many events were checked and how many break a property. It does
not say which events or which instances.

A document can pass every check and still be wrong: the checks take the
instances from the document itself and never expand a rule, so an instance
that is missing, or one that should not be there, goes unnoticed. Events the
package refuses are counted on their own line. Exit status 0 means no check
failed.
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from agenda.data import DataSet  # noqa: E402
from agenda.errors import AgendaError  # noqa: E402
from agenda.output import agenda_rows, event_doc  # noqa: E402

RULES = [
    ("events.md 6", "instances last their duration"),
    ("zones.md 5", "local times and offsets agree with the UTC times"),
    ("zones.md 4", "unmoved instances start at their recurrence id"),
    ("events.md 4.4", "one instance per recurrence id"),
    ("events.md 7", "instances overlap the window"),
    ("output.md 2", "instances in time order"),
    ("output.md 3", "agenda rows match the documents and are sorted"),
]


def _local(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%dT%H:%M")


def _utc(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%dT%H:%MZ")


def _offset(text: str) -> int:
    sign = -1 if text[0] == "-" else 1
    return sign * (int(text[1:3]) * 60 + int(text[4:6]))


def _exists(zone, local: datetime) -> bool:
    """Whether some offset of the zone names this local time (zones.md 4.1)."""
    offsets = {zone.std} | ({zone.dst} if zone.dst is not None else set())
    return any(zone.offset_at(local - timedelta(minutes=o)) == o for o in offsets)


def check_event(raw: dict, doc: dict, zone, window) -> set[str]:
    broken = set()
    overrides = {o.get("recurrence_id"): o for o in raw.get("overrides", []) or []}
    insts = doc["instances"]
    for i in insts:
        start, end = _utc(i["start_utc"]), _utc(i["end_utc"])
        o = overrides.get(i["recurrence_id"])
        duration = o.get("duration_min", raw["duration_min"]) if o and i["overridden"] else raw["duration_min"]
        if end - start != timedelta(minutes=duration):
            broken.add("events.md 6")
        off = zone.offset_at(start)
        if _offset(i["offset"]) != off or _local(i["start"]) != start + timedelta(minutes=off):
            broken.add("zones.md 5")
        if _local(i["end"]) != end + timedelta(minutes=zone.offset_at(end)):
            broken.add("zones.md 5")
        if not i["overridden"]:
            rid = _local(i["recurrence_id"])
            if _exists(zone, rid) and _local(i["start"]) != rid:
                broken.add("zones.md 4")
            if not _exists(zone, rid) and _local(i["start"]) <= rid:
                broken.add("zones.md 4")
        if not (start < window.end and end > window.start):
            broken.add("events.md 7")
    rids = [i["recurrence_id"] for i in insts]
    if len(set(rids)) != len(rids):
        broken.add("events.md 4.4")
    keys = [(i["start_utc"], i["recurrence_id"]) for i in insts]
    if keys != sorted(keys):
        broken.add("output.md 2")
    return broken


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--data", default=str(APP / "data"))
    args = p.parse_args(argv)
    ds = DataSet(args.data)
    counts = {r: 0 for r, _ in RULES}
    checked, refused, docs = 0, 0, []
    for uid in ds.uids():
        raw = json.loads((ds.root / "events" / f"{uid}.json").read_text(encoding="utf-8"))
        try:
            event = ds.event(uid)
            doc = event_doc(event, ds.window)
        except AgendaError:
            refused += 1
            continue
        except Exception as e:  # a crash is a failed check, not a refusal
            print(f"{uid}: {type(e).__name__}: {e}")
            return 2
        checked += 1
        docs.append(doc)
        for rule in check_event(raw, doc, event.zone, ds.window):
            counts[rule] += 1
    rows = agenda_rows(docs)
    expected = sorted(((i["start_utc"], d["uid"], i["recurrence_id"]) for d in docs for i in d["instances"]))
    if [(r["start_utc"], r["uid"], r["recurrence_id"]) for r in rows] != expected:
        counts["output.md 3"] += 1
    for rule, what in RULES:
        print(f"{rule:<14} {what:<52} {checked:>4} checked {counts[rule]:>4} broken")
    print(f"{'refused':<14} {'events the package could not expand':<52} {refused:>4}")
    return 1 if any(counts.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
