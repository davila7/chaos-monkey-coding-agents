"""Consistency checks on the reports the measure package builds from a data directory.

Usage, from /app:

    python tools/check.py [--data DIR]

The tool builds the report of every record in DIR (./data when left out) with
the package and checks properties that every correct report has: written
values that carry the number of significant figures the report states, a value
and an SI value that agree with each other, a dimension that agrees with both
units, reductions that stay within their readings, and a summary listing that
matches the reports. It prints, per rule, how many records were checked and
how many break a property. It does not say which records.

A report can pass every check and still be wrong: the checks read units,
numbers and readings with the package itself and never work a result out on
their own, so a value that is consistent but wrongly converted, rounded or
reduced goes unnoticed. Records the package refuses are counted on their own
line. Exit status 0 means no check failed.
"""

import argparse
import sys
from fractions import Fraction
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from measure.data import DataSet  # noqa: E402
from measure.errors import MeasureError  # noqa: E402
from measure.expr import parse_unit  # noqa: E402
from measure.numbers import NUMBER, exponent, read_number  # noqa: E402
from measure.quantity import parse_quantity  # noqa: E402
from measure.report import report, summary_rows  # noqa: E402

RULES = [
    ("output.md 3", "written values carry the stated significant figures"),
    ("output.md 2", "value and SI value agree"),
    ("units.md 5", "dimension agrees with the unit and the SI unit"),
    ("records.md 3", "a result stays within what its readings allow"),
    ("output.md 4", "summary rows match the reports and are sorted"),
]


def last_step(text: str) -> Fraction:
    """The place value of the last significant digit of a written number."""
    value, sig = read_number(text)
    if value == 0:
        m = NUMBER.fullmatch(text)
        return Fraction(10) ** (int(m.group(5) or 0) - len(m.group(4) or ""))
    return Fraction(10) ** (exponent(value) - sig + 1)


def check_report(rep: dict, record, table) -> set[str]:
    broken = set()
    sig = rep["sig_figs"]
    for text in (rep["value"], rep["si"]["value"]):
        try:
            if read_number(text)[1] != sig:
                broken.add("output.md 3")
        except MeasureError:
            broken.add("output.md 3")
    unit = parse_unit(rep["unit"], table)
    si_unit = parse_unit(rep["si"]["unit"], table)
    if unit.dim.text() != rep["dimension"] or si_unit.dim.text() != rep["dimension"] or si_unit.factor != 1:
        broken.add("units.md 5")
    value, si = read_number(rep["value"])[0], read_number(rep["si"]["value"])[0]
    if rep["kind"] == "difference" or unit.kind == "difference":
        back = value * unit.factor
    elif unit.kind == "absolute":
        back = (value + unit.offset) * unit.factor
    else:
        back = value * unit.factor
    slack = last_step(rep["value"]) * unit.factor / 2 + last_step(rep["si"]["value"]) / 2
    if abs(back - si) > slack:
        broken.add("output.md 2")
    readings = [parse_quantity(t, table).si() for t in record.readings]
    half = last_step(rep["si"]["value"]) / 2
    if rep["reduce"] == "mean" and not min(readings) - half <= si <= max(readings) + half:
        broken.add("records.md 3")
    if rep["reduce"] == "range" and (si < -half or si > max(readings) - min(readings) + half):
        broken.add("records.md 3")
    if rep["reduce"] == "single" and abs(si - readings[0]) > half:
        broken.add("records.md 3")
    return broken


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--data", default=str(APP / "data"))
    args = p.parse_args(argv)
    ds = DataSet(args.data)
    table = ds.table
    counts = {r: 0 for r, _ in RULES}
    checked, refused, reports = 0, 0, []
    for rid in ds.ids():
        try:
            record = ds.record(rid)
            rep = report(record, table)
        except MeasureError:
            refused += 1
            continue
        except Exception as e:  # a crash is a failed check, not a refusal
            print(f"{rid}: {type(e).__name__}: {e}")
            return 2
        checked += 1
        reports.append(rep)
        for rule in check_report(rep, record, table):
            counts[rule] += 1
    rows = summary_rows(reports)
    by_id = {r["id"]: r for r in reports}
    keys = [(r["dimension"], r["id"]) for r in rows]
    if keys != sorted(keys) or len(rows) != len(reports):
        counts["output.md 4"] += 1
    for row in rows:
        rep = by_id.get(row["id"])
        if rep is None or (row["dimension"], row["value"], row["unit"]) != (rep["dimension"], rep["value"], rep["unit"]):
            counts["output.md 4"] += 1
    for rule, what in RULES:
        print(f"{rule:<13} {what:<52} {checked:>4} checked {counts[rule]:>4} broken")
    print(f"{'refused':<13} {'records the package could not report':<52} {refused:>4}")
    return 1 if any(counts.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
