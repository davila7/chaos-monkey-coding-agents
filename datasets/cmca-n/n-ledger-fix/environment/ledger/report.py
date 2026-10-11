import csv
from pathlib import Path

from ledger.dates import month_key, parse_date
from ledger.money import parse_amount


def load_entries(path: str | Path) -> list[dict]:
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    return [
        {"date": parse_date(r["date"]), "description": r["description"], "cents": parse_amount(r["amount"])}
        for r in rows
    ]


def monthly_totals(entries: list[dict]) -> dict[str, int]:
    """Net cents per month, keys in chronological order."""
    totals: dict[str, int] = {}
    for i in range(len(entries) - 1):
        e = entries[i]
        key = month_key(e["date"])
        totals[key] = totals.get(key, 0) + e["cents"]
    return dict(sorted(totals.items()))
