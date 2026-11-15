"""Consistency checks on the documents the gridcalc package evaluates from a data directory.

Usage, from /app:

    python tools/check.py [--data DIR]

The tool evaluates every sheet in DIR (./data when left out) with the package
and checks properties that every correct document has: each defined cell
listed once and in cell order, values whose JSON type fits their cell type,
refs listings in order and without repeats, and a summary listing that matches
the documents. It prints, per rule, how many sheets were checked and how many
break a property. It does not say which sheets.

A document can pass every check and still be wrong: the checks evaluate with
the package itself and never work a value out on their own, so a value that is
well formed but wrongly tokenized, parsed, converted or evaluated goes
unnoticed. Refused sheets are counted on their own line. Exit status 0 means
no check failed.
"""

import argparse
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from gridcalc.errors import SheetError  # noqa: E402
from gridcalc.refs import cell_key, ref_key  # noqa: E402
from gridcalc.report import document, summary_rows  # noqa: E402
from gridcalc.sheets import DataSet  # noqa: E402
from gridcalc.values import CODES  # noqa: E402

RULES = [
    ("output.md 2.2", "every defined cell once, in cell order"),
    ("output.md 2.4", "values have the JSON type of their cell type"),
    ("output.md 2.5", "refs listings in order, without repeats"),
    ("output.md 3", "summary rows match the documents and are sorted"),
]


def type_fits(kind: str, value) -> bool:
    if kind == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if kind == "bool":
        return isinstance(value, bool)
    if kind == "text":
        return isinstance(value, str)
    if kind == "error":
        return value in CODES
    return False


def check_doc(doc: dict, sheet) -> set[str]:
    broken = set()
    names = [c["cell"] for c in doc["cells"]]
    if names != sorted(sheet.cells, key=cell_key):
        broken.add("output.md 2.2")
    for c in doc["cells"]:
        if not type_fits(c["type"], c["value"]):
            broken.add("output.md 2.4")
        if "formula" in c:
            refs = c.get("refs")
            if not isinstance(refs, list) or len(set(refs)) != len(refs) or refs != sorted(refs, key=ref_key):
                broken.add("output.md 2.5")
    return broken


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--data", default=str(APP / "data"))
    args = p.parse_args(argv)
    ds = DataSet(args.data)
    counts = {r: 0 for r, _ in RULES}
    checked, refused, docs = 0, 0, []
    for sid in ds.ids():
        try:
            sheet = ds.sheet(sid)
            doc = document(sheet)
        except SheetError:
            refused += 1
            continue
        except Exception as e:  # a crash is a failed check, not a refusal
            print(f"{sid}: {type(e).__name__}: {e}")
            return 2
        checked += 1
        docs.append(doc)
        for rule in check_doc(doc, sheet):
            counts[rule] += 1
    rows = summary_rows(docs)
    by_id = {d["sheet"]: d for d in docs}
    if [r["sheet"] for r in rows] != sorted(by_id) or len(rows) != len(docs):
        counts["output.md 3"] += 1
    for row in rows:
        d = by_id.get(row["sheet"])
        want = None if d is None else (len(d["cells"]), sum(1 for c in d["cells"] if "formula" in c), sum(1 for c in d["cells"] if c["type"] == "error"))
        if want != (row["cells"], row["formulas"], row["errors"]):
            counts["output.md 3"] += 1
    for rule, what in RULES:
        print(f"{rule:<14} {what:<50} {checked:>4} checked {counts[rule]:>4} broken")
    print(f"{'refused':<14} {'sheets the package could not read':<50} {refused:>4}")
    return 1 if any(counts.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
