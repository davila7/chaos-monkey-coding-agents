"""The standard reports (docs/exports.md 3)."""

from datetime import date
from pathlib import Path

from . import rates, reorder, units
from .catalog import Catalog
from .export import write_report
from .ledger import Ledger

STOCK_COLUMNS = ["sku", "name", "on_hand", "unit_weight", "total_weight", "tags"]
AGING_COLUMNS = ["sku", "lot", "qty", "age_days"]
REORDER_COLUMNS = ["sku", "on_hand", "reorder_point", "order_qty", "review"]
FREIGHT_COLUMNS = ["sku", "billable_kg", "price"]


def stock_report(ledger: Ledger, catalog: Catalog, settings: dict, target: Path, site: str | None = None) -> int:
    site = site or settings["site"]
    rows = []
    for item in catalog:
        have = ledger.on_hand(item.sku, site)
        if not have:
            continue
        rows.append([
            item.sku,
            item.name,
            have,
            units.format_weight(item.weight_g, settings),
            units.format_weight(item.weight_g * have, settings),
            " ".join(item.tag_list()),
        ])
    return write_report(target, STOCK_COLUMNS, rows)


def aging_report(ledger: Ledger, target: Path, as_of: date | None = None, site: str = "main", older_than: int = 0) -> int:
    rows = [list(r) for r in ledger.aging(as_of, site) if r[3] >= older_than]
    return write_report(target, AGING_COLUMNS, rows)


def reorder_report(ledger: Ledger, catalog: Catalog, settings: dict, target: Path, as_of: date | None = None) -> int:
    rows = [
        [s.sku, s.on_hand, s.reorder_point, s.order_qty, s.review.isoformat()]
        for s in reorder.suggestions(ledger, catalog, settings, as_of, settings["site"])
    ]
    return write_report(target, REORDER_COLUMNS, rows)


def freight_sheet(catalog: Catalog, spec: dict, zone, target: Path) -> int:
    t = rates.table(spec)
    rows = [
        [item.sku, rates.billable_kg(item.weight_g, item.dims_mm), rates.format_cents(rates.quote(spec, item.weight_g, zone, item.dims_mm), t.currency)]
        for item in catalog
    ]
    return write_report(target, FREIGHT_COLUMNS, rows)
