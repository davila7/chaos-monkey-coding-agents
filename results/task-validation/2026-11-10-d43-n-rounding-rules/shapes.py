"""Counts the trap shapes in the visible samples and in the held-out data (for WALKTHROUGH.md)."""
import json
import sys
import tempfile
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal
from pathlib import Path

# Usage: python3 shapes.py ORIG_ROOT TASK_DIR, ORIG_ROOT built by TASK_DIR/tests/gen/build.py.
orig, T = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(orig))
sys.path.insert(0, str(T / "tests"))
import heldout  # noqa
from meterbill import bill, credits, model, tariffs  # noqa

C = Decimal("0.01")


def shapes(docs_books):
    n = dict(accounts=0, band_tie=0, eff_tie=0, credit_float=0, credit_negzero=0, cash_tie=0, avg_tie=0, use_tie=0, zero_seg=0, neg_seg=0)
    for doc, book in docs_books:
        n["accounts"] += 1
        a = model.parse(doc)
        b = bill.compute(a, book)
        t = b.tariff
        for c in b.bands:
            x = c.kwh * c.price
            n["band_tie"] += x.quantize(C, ROUND_HALF_UP) != x.quantize(C, ROUND_HALF_EVEN)
        if b.kwh:
            x = b.energy / b.kwh
            q = Decimal("0.0001")
            n["eff_tie"] += x.quantize(q, ROUND_HALF_UP) != x.quantize(q, ROUND_HALF_EVEN)
        for c in a.credits:
            n["credit_float"] += credits.settle(c.amount) != float(Decimal(repr(c.amount)).quantize(C, ROUND_HALF_UP))
        n["credit_negzero"] += str(b.credits) == "-0.00"
        rule = book.cash[t.currency]
        if rule != "none":
            step = Decimal(1) if rule == "whole" else Decimal(rule)
            n["cash_tie"] += (b.total / step) % 1 in (Decimal("0.5"), Decimal("-0.5"))
        avg = float(b.total) / b.days
        n["avg_tie"] += format(avg, ".2f") != str(Decimal(repr(avg)).quantize(C, ROUND_HALF_UP))
        use = float(b.kwh) / b.days
        n["use_tie"] += format(use, ".1f") != str(Decimal(repr(use)).quantize(Decimal("0.1"), ROUND_HALF_UP))
        n["zero_seg"] += any(s.rate == 0 for s in a.standing)
        n["neg_seg"] += any(s.rate < 0 for s in a.standing)
    return n


book = tariffs.load_book(orig / "meterbill" / "data" / "tariffs.json")
vis = [(json.loads(p.read_text()), book) for p in sorted((orig / "samples" / "accounts").glob("*.json"))]
print("visible", shapes(vis))
d = Path(tempfile.mkdtemp())
cmds = heldout.make(d, orig)
books = {"a": tariffs.load_book(d / "book-a.json"), "b": tariffs.load_book(d / "book-b.json"), "d": book}
held = [(json.loads(p.read_text()), books[k]) for k in "abd" for p in sorted((d / k).glob("*.json"))]
print("held-out", shapes(held), "commands", len(cmds))
