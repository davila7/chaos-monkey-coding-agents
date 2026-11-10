"""A quote: what a given consumption over a number of days would cost."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from meterbill import cash, standing, tariffs, tax
from meterbill.errors import BillError
from meterbill.model import Segment
from meterbill.tariffs import Book, Tariff

ORIGIN = date(2000, 1, 1)


@dataclass(frozen=True)
class Quote:
    tariff: Tariff
    kwh: Decimal
    days: int
    bands: tuple
    energy: Decimal
    standing: Decimal
    subtotal: Decimal
    vat: Decimal
    total: Decimal
    payable: Decimal


def estimate(book: Book, tariff_name: str, kwh: Decimal, days: int) -> Quote:
    if days < 1:
        raise BillError("days must be at least 1")
    if kwh < 0:
        raise BillError("kWh must not be negative")
    tariff = book.tariff(tariff_name)
    bands = tariffs.charge_bands(kwh, tariff)
    energy = tariffs.energy_total(bands)
    seg = Segment(ORIGIN, ORIGIN + timedelta(days=days - 1), tariff.standing)
    standing_total = standing.prorate([seg])[0]
    subtotal = energy + standing_total
    vat = tax.vat(subtotal, tariff.vat)
    total = subtotal + vat
    return Quote(
        tariff=tariff,
        kwh=kwh,
        days=days,
        bands=tuple(bands),
        energy=energy,
        standing=standing_total,
        subtotal=subtotal,
        vat=vat,
        total=total,
        payable=cash.payable(total, book.cash[tariff.currency]),
    )
