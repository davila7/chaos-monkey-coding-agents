import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from ledger.dates import parse_date
from ledger.errors import FormatError
from ledger.money import parse_amount

IMPLIED = {"delimiter": ",", "decimal": ".", "date_order": "ymd"}


@dataclass(frozen=True)
class Entry:
    id: str
    date: date
    description: str
    cents: int
    reverses: str | None = None


@dataclass(frozen=True)
class Statement:
    account: str
    currency: str
    entries: list[Entry]


def read_header(lines: list[str]) -> tuple[dict[str, str], int]:
    header = dict(IMPLIED)
    n = 0
    for line in lines:
        if not line.startswith("#"):
            break
        key, sep, value = line[1:].partition(":")
        if not sep:
            raise FormatError(f"bad header line: {line!r}")
        header[key.strip()] = value.strip()
        n += 1
    for required in ("account", "currency"):
        if required not in header:
            raise FormatError(f"missing header field: {required}")
    return header, n


def read_statement(path: str | Path) -> Statement:
    lines = Path(path).read_text().splitlines()
    header, n = read_header(lines)
    rows = csv.DictReader(lines[n:], delimiter=header["delimiter"])
    entries = [
        Entry(
            id=r["id"].strip(),
            date=parse_date(r["date"], header["date_order"]),
            description=r["description"].strip(),
            cents=parse_amount(r["amount"], header["decimal"]),
            reverses=(r.get("reverses") or "").strip() or None,
        )
        for r in rows
    ]
    return Statement(header["account"], header["currency"], entries)
