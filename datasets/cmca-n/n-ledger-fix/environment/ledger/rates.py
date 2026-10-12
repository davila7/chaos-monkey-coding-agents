import csv
from pathlib import Path

from ledger.errors import MissingRate

BASE = "USD"


class Rates:
    """Monthly rates: how many USD one unit of a currency was worth that month."""

    def __init__(self, table: dict[tuple[str, str], str]):
        self._table = table

    def rate(self, currency: str, month: str) -> str:
        if currency == BASE:
            return "1"
        try:
            return self._table[(month, currency)]
        except KeyError:
            raise MissingRate(f"no {currency} rate for {month}") from None


def load_rates(path: str | Path) -> Rates:
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    return Rates({(r["month"], r["currency"]): r["usd_per_unit"].strip() for r in rows})
