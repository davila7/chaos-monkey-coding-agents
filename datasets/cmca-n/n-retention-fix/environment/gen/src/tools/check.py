"""Consistency checks on the plans the retain package makes for a data directory.

Usage, from /app:

    python tools/check.py [--data DIR]

The tool plans every set in DIR (./data when left out) with the package and
checks properties that every correct plan has: every listed name in exactly
one of keep, prune and ignored; keep and prune holding only backups of the set;
lists in their order; reasons in their order without repeats; and a summary
listing that matches the plans. It prints, per rule, how many sets were
checked and how many break a property. It does not say which sets.

A plan can pass every check and still be wrong: the checks read names and
zones with the package itself and never decide on their own which backups a
policy keeps, so a backup kept or pruned for the wrong reason, or at the wrong
instant, goes unnoticed. Sets the package refuses are counted on their own
line. Exit status 0 means no check failed.
"""

import argparse
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from retain.data import DataSet  # noqa: E402
from retain.errors import PlanError  # noqa: E402
from retain.names import iso, parse_name  # noqa: E402
from retain.plan import plan, summary_rows  # noqa: E402
from retain.rules import REASONS  # noqa: E402

RULES = [
    ("output.md 2.6", "each listed name once in keep, prune or ignored"),
    ("names.md 4", "keep and prune hold only backups of the set"),
    ("output.md 2", "keep and prune latest first, other lists sorted"),
    ("rules.md 2", "reasons present, in order, once each, pins kept"),
    ("output.md 3", "summary rows match the plans and are sorted"),
]


def check_plan(p: dict, ds: DataSet) -> set[str]:
    broken = set()
    s = ds.load(p["set"])
    kept = [k["name"] for k in p["keep"]]
    placed = kept + p["prune"] + p["ignored"]
    if sorted(placed) != sorted(s.files):
        broken.add("output.md 2.6")
    backups = {}
    for name in kept + p["prune"]:
        b = parse_name(name, s.prefix, s.zone)
        if b is None:
            broken.add("names.md 4")
        else:
            backups[name] = b
    for names in (kept, p["prune"]):
        known = [backups[n] for n in names if n in backups]
        keys = [(-b.at.timestamp(), b.name) for b in known]
        if keys != sorted(keys):
            broken.add("output.md 2")
    for k in p["keep"]:
        if k["name"] in backups and k["at"] != iso(backups[k["name"]].at):
            broken.add("output.md 2")
    if p["ignored"] != sorted(p["ignored"]) or p["missing_pins"] != sorted(set(p["missing_pins"])):
        broken.add("output.md 2")
    for k in p["keep"]:
        r = k["reasons"]
        if not r or len(set(r)) != len(r) or any(x not in REASONS for x in r) or r != sorted(r, key=REASONS.index):
            broken.add("rules.md 2")
    reasons = {k["name"]: k["reasons"] for k in p["keep"]}
    for pin in s.pins:
        if pin in backups or pin in p["prune"]:
            if "pinned" not in reasons.get(pin, []):
                broken.add("rules.md 2")
    return broken


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(APP / "data"))
    args = ap.parse_args(argv)
    ds = DataSet(args.data)
    counts = {r: 0 for r, _ in RULES}
    checked, refused, plans = 0, 0, []
    for sid in ds.ids():
        try:
            p = plan(ds, sid)
        except PlanError:
            refused += 1
            continue
        except Exception as e:  # a crash is a failed check, not a refusal
            print(f"{sid}: {type(e).__name__}: {e}")
            return 2
        checked += 1
        plans.append(p)
        for rule in check_plan(p, ds):
            counts[rule] += 1
    rows = summary_rows(plans)
    by_id = {p["set"]: p for p in plans}
    if [r["set"] for r in rows] != sorted(by_id) or len(rows) != len(plans):
        counts["output.md 3"] += 1
    for row in rows:
        p = by_id.get(row["set"])
        want = None if p is None else (len(p["keep"]), len(p["prune"]), len(p["ignored"]), len(p["missing_pins"]))
        if want != (row["kept"], row["pruned"], row["ignored"], row["missing_pins"]):
            counts["output.md 3"] += 1
    for rule, what in RULES:
        print(f"{rule:<14} {what:<50} {checked:>4} checked {counts[rule]:>4} broken")
    print(f"{'refused':<14} {'sets the package could not plan':<50} {refused:>4}")
    return 1 if any(counts.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
