"""Reorder points, order suggestions and review dates (docs/stock.md 5 and 6)."""

import calendar
import math
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_EVEN, Decimal

from . import clock
from .catalog import Catalog
from .errors import SettingsError
from .ledger import Ledger


@dataclass(frozen=True)
class Suggestion:
    sku: str
    on_hand: int
    reorder_point: int
    order_qty: int
    review: date


def daily_demand(ledger: Ledger, sku: str, settings: dict, as_of: date | None = None, site: str = "main") -> Decimal:
    """Mean units issued per day over the demand_days days that end on as_of."""
    as_of = as_of or clock.today()
    days = settings["reorder"]["demand_days"]
    if days <= 0:
        raise SettingsError("reorder.demand_days must be at least 1")
    issued = ledger.issued(sku, as_of - timedelta(days=days - 1), as_of, site)
    return (Decimal(issued) / days).quantize(Decimal("0.0001"), rounding=ROUND_HALF_EVEN)


def reorder_point(demand: Decimal, lead_days: int, settings: dict) -> int:
    return math.ceil(demand * (lead_days + settings["reorder"]["safety_days"]))


def next_review(last: date | None = None, settings: dict | None = None) -> date:
    """The review after the one on last (stock.md 6)."""
    last = last or clock.today()
    day = ((settings or {}).get("reorder") or {}).get("review_day") or last.day
    if not isinstance(day, int) or not 1 <= day <= 31:
        raise SettingsError("reorder.review_day must be a day of the month")
    y, m = (last.year + 1, 1) if last.month == 12 else (last.year, last.month + 1)
    return date(y, m, min(day, calendar.monthrange(y, m)[1]))


def suggestions(ledger: Ledger, catalog: Catalog, settings: dict, as_of: date | None = None, site: str = "main") -> list[Suggestion]:
    """One suggestion per item whose stock is at or below its reorder point, by sku."""
    as_of = as_of or clock.today()
    review = next_review(as_of, settings)
    out = []
    for item in catalog:
        demand = daily_demand(ledger, item.sku, settings, as_of, site)
        point = reorder_point(demand, item.lead_days, settings)
        have = ledger.on_hand(item.sku, site)
        if point == 0 or have > point:
            continue
        cover = math.ceil(demand * (review - as_of).days)
        want = point + cover - have
        cases = max(1, math.ceil(want / item.case_qty))
        out.append(Suggestion(item.sku, have, point, cases * item.case_qty, review))
    return out
