"""Quoting a CSV file of shipments.

Columns: id, from, to, weight, dims (optional), residential (optional, yes/no),
value (optional). The cheapest quote is taken for each row.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal

from quoter.core.errors import InputError, QuoterError
from quoter.core.money import cents
from quoter.pricing import discounts
from quoter.pricing.tax import apply_tax
from quoter.services.quotes import cheapest, make_request

REQUIRED = ("id", "from", "to", "weight")


@dataclass
class BatchLine:
    ident: str
    quote: object
    error: str | None = None


@dataclass
class BatchResult:
    lines: list
    net_total: Decimal
    discount_pct: Decimal
    discount: Decimal
    total: Decimal


def read_rows(path: str) -> list:
    try:
        with open(path, encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
    except OSError as exc:
        raise InputError(f"cannot read {path}: {exc.strerror}") from None
    if rows:
        missing = [c for c in REQUIRED if c not in rows[0]]
        if missing:
            raise InputError(f"{path}: missing column(s) {', '.join(missing)}")
    return rows


def run_batch(path: str) -> BatchResult:
    lines = []
    for row in read_rows(path):
        ident = (row.get("id") or "").strip() or "?"
        try:
            req = make_request(
                row["from"],
                row["to"],
                row["weight"],
                (row.get("dims") or "").strip() or None,
                (row.get("residential") or "").strip().lower() in ("yes", "y", "1", "true"),
                (row.get("value") or "").strip() or None,
            )
            q = cheapest(req)
            lines.append(BatchLine(ident, q, None if q else "no carrier takes this shipment"))
        except QuoterError as exc:
            lines.append(BatchLine(ident, None, str(exc)))
    quoted = [l.quote for l in lines if l.quote is not None]
    net_total = sum((q.net for q in quoted), Decimal(0))
    pct = discounts.discount_pct(len(quoted))
    discount = cents(net_total * pct / 100)
    total = apply_tax(net_total - discount)
    return BatchResult(lines, net_total, pct, discount, total)
