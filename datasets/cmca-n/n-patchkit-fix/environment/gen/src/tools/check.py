"""Consistency checks on the results the patchkit package writes for a data directory.

Usage, from /app:

    python tools/check.py [--data DIR]

The tool applies every case in DIR (./data when left out) with the package and
checks properties that every correct result has: every file of the case in
exactly one of files and untouched; entries in the order of the sections;
hunk reports numbered in order, with fields that agree with their result;
offsets that agree with the stated lines; a status and content that agree
with the reports; and a summary listing that matches the results. It prints,
per rule, how many cases were checked and how many break a property. It does
not say which cases.

A result can pass every check and still be wrong: the checks parse patches
with the package itself and never decide on their own where a hunk belongs,
so a hunk applied at the wrong place, or rejected when it should apply, goes
unnoticed. Offsets are checked only for hunks that applied without fuzz.
Cases the package refuses are counted on their own line. Exit status 0 means
no check failed.
"""

import argparse
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from patchkit.cases import DataSet  # noqa: E402
from patchkit.errors import PatchError  # noqa: E402
from patchkit.report import result, sections_of, summary_rows  # noqa: E402

RULES = [
    ("output.md 2.1", "each file of the case once in files or untouched"),
    ("output.md 2.2", "entries in patch order, with the action of their section"),
    ("output.md 2.4", "hunk reports numbered in order, fields agree with result"),
    ("apply.md 3.6", "offset of a hunk applied without fuzz is line minus A"),
    ("output.md 2.3", "status and content agree with the hunk reports"),
    ("output.md 3", "summary rows match the results and are sorted"),
]


def check_result(r: dict, ds: DataSet) -> set[str]:
    broken = set()
    case = ds.load(r["case"])
    sections = sections_of(case)
    paths = [e["path"] for e in r["files"]]
    if sorted(paths + r["untouched"]) != sorted(set(case.files) | {p for _, a, p in sections if a == "create"}):
        broken.add("output.md 2.1")
    if r["untouched"] != sorted(r["untouched"]) or len(set(paths)) != len(paths):
        broken.add("output.md 2.1")
    if paths != [p for _, _, p in sections] or [e["action"] for e in r["files"]] != [a for _, a, _ in sections]:
        broken.add("output.md 2.2")
    by_path = {p: s for s, _, p in sections}
    for e in r["files"]:
        s = by_path.get(e["path"])
        if s is None or [h["hunk"] for h in e["hunks"]] != [h.number for h in s.hunks]:
            broken.add("output.md 2.4")
            continue
        stated = {h.number: h.old_start for h in s.hunks}
        for rep in e["hunks"]:
            values = [rep["line"], rep["offset"], rep["fuzz"]]
            if rep["result"] == "applied":
                if not all(isinstance(v, int) for v in values) or not 0 <= rep["fuzz"] <= case.fuzz:
                    broken.add("output.md 2.4")
                elif rep["fuzz"] == 0 and rep["offset"] != rep["line"] - stated[rep["hunk"]]:
                    broken.add("apply.md 3.6")
            elif rep["result"] != "rejected" or values != [None, None, None]:
                broken.add("output.md 2.4")
        applied = sum(rep["result"] == "applied" for rep in e["hunks"])
        want = "applied" if applied == len(e["hunks"]) else "partial" if applied else "rejected"
        if e["action"] == "delete" and want == "applied" and e["content"] is not None:
            want = "partial"
        if e["status"] != want:
            broken.add("output.md 2.3")
        deleted = e["action"] == "delete" and e["status"] == "applied"
        unmade = e["action"] == "create" and e["status"] == "rejected"
        if (e["content"] is None) != (deleted or unmade):
            broken.add("output.md 2.3")
        if e["status"] == "rejected" and e["action"] != "create" and e["content"] != case.files.get(e["path"]):
            broken.add("output.md 2.3")
    return broken


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(APP / "data"))
    args = ap.parse_args(argv)
    ds = DataSet(args.data)
    counts = {rule: 0 for rule, _ in RULES}
    checked, refused, results = 0, 0, []
    for cid in ds.ids():
        try:
            r = result(ds, cid)
        except PatchError:
            refused += 1
            continue
        except Exception as e:  # a crash is a failed check, not a refusal
            print(f"{cid}: {type(e).__name__}: {e}")
            return 2
        checked += 1
        results.append(r)
        for rule in check_result(r, ds):
            counts[rule] += 1
    rows = summary_rows(results)
    by_id = {r["case"]: r for r in results}
    if [row["case"] for row in rows] != sorted(by_id) or len(rows) != len(results):
        counts["output.md 3"] += 1
    for row in rows:
        r = by_id.get(row["case"])
        if r is None:
            continue
        reps = [h for e in r["files"] for h in e["hunks"]]
        done = [h for h in reps if h["result"] == "applied"]
        want = [len(r["files"]), len(reps), len(done), sum(h["offset"] != 0 for h in done), sum(h["fuzz"] != 0 for h in done), len(reps) - len(done)]
        if [row["files"], row["hunks"], row["applied"], row["moved"], row["fuzzed"], row["rejected"]] != want:
            counts["output.md 3"] += 1
    for rule, what in RULES:
        print(f"{rule:<14} {what:<58} {checked:>4} checked {counts[rule]:>4} broken")
    print(f"{'refused':<14} {'cases the package could not apply':<58} {refused:>4}")
    return 1 if any(counts.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
