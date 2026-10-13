"""Quarterly tax returns.

A return groups the taxed lines of one or more statements of a jurisdiction by
calendar quarter of their valuation date. Lines are the per-entry values of
``ledger.report.vat.taxed_lines``; the return only adds them up.

    {"jurisdiction": "ARD", "quarters": {"2026-Q1": {"S": {...}, "R": {...}, "tax": 1234}}, "tax": 1234}
"""

from datetime import date

from ledger.fx.table import RateTable
from ledger.periods.months import month_key, quarter


def quarter_key(d: date) -> str:
    return f"{d.year:04d}-Q{quarter(month_key(d))}"


def build_return(statements, table: RateTable) -> dict:
    from ledger.book.reversals import bookings
    from ledger.report.vat import taxed_lines

    jurisdictions = {s.jurisdiction for s in statements}
    if len(jurisdictions) != 1 or "" in jurisdictions:
        raise ValueError("a return covers statements of exactly one jurisdiction")
    quarters: dict[str, dict] = {}
    for s in statements:
        valuation = {b.entry.id: b.valuation_date for b in bookings(s.entries)}
        for line in taxed_lines(s, table):
            q = quarter_key(valuation[line["id"]])
            bucket = quarters.get(q) or {"tax": 0}
            quarters[q] = bucket
            code = bucket.get(line["code"]) or {"gross": 0, "net": 0, "tax": 0}
            bucket[line["code"]] = code
            for k in ("gross", "net", "tax"):
                code[k] += line[k]
            bucket["tax"] += line["tax"]
    ordered = {q: dict(sorted(v.items())) for q, v in sorted(quarters.items())}
    return {"jurisdiction": jurisdictions.pop(), "quarters": ordered, "tax": sum(v["tax"] for v in ordered.values())}
