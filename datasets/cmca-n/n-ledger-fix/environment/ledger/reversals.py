from dataclasses import dataclass
from datetime import date

from ledger.statement import Entry


@dataclass(frozen=True)
class Booking:
    entry: Entry
    month_date: date
    rate_date: date


def bookings(entries: list[Entry]) -> list[Booking]:
    """Pairs every entry with the date that decides its month and the date that decides its rate."""
    by_id = {e.id: e for e in entries}
    out = []
    for e in entries:
        original = by_id.get(e.reverses) if e.reverses else None
        if original is None:
            out.append(Booking(e, e.date, e.date))
        else:
            out.append(Booking(e, original.date, e.date))
    return out
