"""Reconciliation of the documents the billing package builds from a data directory.

Usage, from /app:

    python tools/reconcile.py [--data DIR]

The tool builds every invoice and credit note in DIR (./data when left out)
with the package, then recomputes selected figures of each document from the
order or credit request and the document's own fields, following the docs.
It prints, per rule, how many documents were checked and how many disagree.
It does not say which documents or which figures disagree.

The checks cover a subset of the rules. Figures that a check takes from the
document itself (the unit price a line shows, the tax percent a line shows)
are not checked against the catalog or the tax table. Exit status 0 means no
check failed and every document could be built, except credit requests that
the package refuses with a credit error; those are counted on their own line.
"""

import argparse
import json
import sys
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from billing.credits.notes import credit_for  # noqa: E402
from billing.data import DataSet  # noqa: E402
from billing.errors import BillingError, CreditError  # noqa: E402
from billing.invoices.builder import invoice_for  # noqa: E402

RULES = [
    ("catalog.md 4", "line gross from quantity, unit price and used days"),
    ("subscriptions.md 2", "billing periods counted from the anchor"),
    ("subscriptions.md 3", "used days of a period"),
    ("discounts.md 2", "line discounts"),
    ("discounts.md 3", "order discounts"),
    ("discounts.md 5", "order discount shares of the lines"),
    ("tax.md 5", "tax amounts by rounding mode"),
    ("tax.md 7", "document totals"),
    ("credit-notes.md 3", "credited amounts"),
]


def rnd(value) -> int:
    return int(Decimal(value).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def month_end(y: int, m: int) -> int:
    nxt = date(y + (m == 12), m % 12 + 1, 1)
    return (nxt - timedelta(days=1)).day


def nth_start(anchor: date, n: int) -> date:
    idx = anchor.year * 12 + anchor.month - 1 + n
    y, m = idx // 12, idx % 12 + 1
    return date(y, m, min(anchor.day, month_end(y, m)))


def minor(text: str, exp: int) -> Decimal:
    return Decimal(text).scaleb(exp)


def apply_discounts(amount: int, discounts: list, exp: int) -> int:
    ordered = [d for d in discounts if d["kind"] == "percent"] + [d for d in discounts if d["kind"] == "amount"]
    for d in ordered:
        if d["kind"] == "percent":
            amount -= rnd(Decimal(amount) * Decimal(d["value"]) / 100)
        else:
            amount = max(0, amount - int(minor(d["value"], exp)))
    return amount


def shares(total: int, weights: list) -> list:
    whole = sum(weights)
    if total == 0 or whole == 0:
        return [0] * len(weights)
    out = [total * w // whole for w in weights]
    rems = [total * w % whole for w in weights]
    for i in sorted(range(len(weights)), key=lambda i: (-rems[i], i))[: total - sum(out)]:
        out[i] += 1
    return out


def part(amount: int, percent: str, inclusive: bool) -> Decimal:
    r = Decimal(percent) / 100
    return Decimal(amount) * r / (1 + r) if inclusive else Decimal(amount) * r


def expected_taxes(lines: list, rounding: str, inclusive: bool, sign: int) -> tuple:
    groups: dict = {}
    line_tax = []
    for l in lines:
        if l["tax_percent"] is None:
            line_tax.append(None)
            continue
        a = sign * l["amount"]
        key = (l["tax_category"], Decimal(l["tax_percent"]))
        g = groups.get(key) or {"amount": 0, "exact": Decimal(0), "tax": 0}
        groups[key] = g
        g["amount"] += a
        if rounding == "line":
            t = rnd(part(a, l["tax_percent"], inclusive))
            g["tax"] += t
            line_tax.append(sign * t)
        else:
            g["exact"] += part(a, l["tax_percent"], inclusive)
            line_tax.append(None)
    tax = 0
    for g in groups.values():
        if rounding == "invoice":
            g["tax"] = rnd(g["exact"])
        tax += g["tax"]
    return line_tax, sign * tax


class Tally:
    def __init__(self):
        self.checked = {r: 0 for r, _ in RULES}
        self.failed = {r: 0 for r, _ in RULES}

    def add(self, rule: str, ok: bool) -> None:
        self.checked[rule] += 1
        self.failed[rule] += 0 if ok else 1


def check_invoice(inv: dict, order: dict, ds: DataSet, t: Tally) -> None:
    exp = ds.currencies.get(inv["currency"]).exponent
    juris = ds.tax.get(inv["jurisdiction"])
    ok_gross = ok_period = ok_used = ok_line = True
    for l, src in zip(inv["lines"], order["lines"]):
        exact = minor(l["unit_price"], exp) * l["qty"]
        p = l["period"]
        sub = src.get("subscription")
        if sub:
            anchor = date.fromisoformat(sub["anchor"])
            n = int(sub["period"])
            start, nxt = nth_start(anchor, n), nth_start(anchor, n + 1)
            end = nxt - timedelta(days=1)
            if p is None or (p["start"], p["end"]) != (start.isoformat(), end.isoformat()):
                ok_period = False
            if p is not None:
                first = max(date.fromisoformat(p["start"]), date.fromisoformat(sub.get("active_from") or p["start"]))
                last = min(date.fromisoformat(p["end"]), date.fromisoformat(sub.get("active_to") or p["end"]))
                days = (date.fromisoformat(p["end"]) - date.fromisoformat(p["start"])).days + 1
                if (p["days"], p["used_days"]) != (days, (last - first).days + 1):
                    ok_used = False
                exact = exact * p["used_days"] / p["days"]
        if rnd(exact) != l["gross"]:
            ok_gross = False
        if apply_discounts(l["gross"], src.get("discounts") or [], exp) != l["gross"] - l["line_discount"]:
            ok_line = False
    t.add("catalog.md 4", ok_gross)
    if any(src.get("subscription") for src in order["lines"]):
        t.add("subscriptions.md 2", ok_period)
        t.add("subscriptions.md 3", ok_used)
    if any(src.get("discounts") for src in order["lines"]):
        t.add("discounts.md 2", ok_line)
    eligible = [l for l in inv["lines"] if not ds.catalog.get(l["sku"]).no_discount]
    after_line = [l["gross"] - l["line_discount"] for l in eligible]
    if order.get("discounts"):
        want = sum(after_line) - apply_discounts(sum(after_line), order["discounts"], exp)
        t.add("discounts.md 3", want == inv["order_discount"])
        t.add("discounts.md 5", shares(inv["order_discount"], after_line) == [l["order_discount"] for l in eligible])
    line_tax, tax = expected_taxes(inv["lines"], juris.rounding, juris.prices_include_tax, 1)
    t.add("tax.md 5", line_tax == [l["tax"] for l in inv["lines"]] and tax == inv["tax"])
    amounts = sum(l["amount"] for l in inv["lines"])
    total_ok = inv["net"] + inv["tax"] == inv["total"] and (inv["total"] == amounts if juris.prices_include_tax else inv["net"] == amounts)
    t.add("tax.md 7", total_ok and sum(g["tax"] for g in inv["taxes"]) == inv["tax"])


def check_credits(docs: list, invoice: dict, ds: DataSet, t: Tally) -> None:
    juris = ds.tax.get(invoice["jurisdiction"])
    by_line = {l["line"]: l for l in invoice["lines"]}
    done_q: dict = {}
    done_a: dict = {}
    for doc, req in docs:
        ok = True
        for l, (n, q) in zip(doc["lines"], [(x["line"], x["qty"]) for x in req["lines"]]):
            src = by_line[n]
            if done_q.get(n, 0) + q == src["qty"]:
                want = src["amount"] - done_a.get(n, 0)
            else:
                want = rnd(Decimal(src["amount"] * q) / src["qty"])
            done_q[n] = done_q.get(n, 0) + q
            done_a[n] = done_a.get(n, 0) + want
            ok = ok and l["amount"] == -want
        t.add("credit-notes.md 3", ok)
        line_tax, tax = expected_taxes(doc["lines"], juris.rounding, juris.prices_include_tax, -1)
        t.add("tax.md 5", line_tax == [l["tax"] for l in doc["lines"]] and tax == doc["tax"])
        t.add("tax.md 7", doc["net"] + doc["tax"] == doc["total"] and doc["total"] <= 0)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python tools/reconcile.py")
    ap.add_argument("--data")
    args = ap.parse_args(argv)
    ds = DataSet(args.data or APP / "data")
    t = Tally()
    errors = 0
    refused = 0
    invoices = {}
    for oid in ds.order_ids():
        order = ds.raw_order(oid)
        try:
            inv = invoice_for(oid, ds)
        except BillingError:
            errors += 1
            continue
        invoices[inv["number"]] = inv
        check_invoice(inv, order, ds, t)
    pending: dict = {}
    for number in ds.credit_ids():
        req = ds.raw_credit(number)
        try:
            doc = credit_for(number, ds)
        except CreditError:
            refused += 1
            continue
        except BillingError:
            errors += 1
            continue
        pending[req["invoice"]] = pending.get(req["invoice"], []) + [(doc, req)]
    for number, docs in sorted(pending.items()):
        if number in invoices:
            docs.sort(key=lambda d: (d[1]["date"], d[1]["number"]))
            check_credits(docs, invoices[number], ds, t)
    width = max(len(title) for _, title in RULES)
    print(f"{'rule':<20} {'':<{width}} checked  disagree")
    for rule, title in RULES:
        print(f"{rule:<20} {title:<{width}} {t.checked[rule]:>7}  {t.failed[rule]:>8}")
    print(f"{'':<20} {'documents the package could not build':<{width}} {'':>7}  {errors:>8}")
    print(f"credit requests refused under credit-notes.md 6 (not counted as disagreements): {refused}")
    bad = sum(t.failed.values()) + errors
    print("all checks agree" if not bad else f"{bad} disagreements")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
