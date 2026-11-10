"""Bin layout and putaway (docs/bins.md)."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .catalog import Item
from .errors import BinError, NoBinError

CODE = re.compile(r"^([A-Z])-(\d{2})-([1-9])$")


def parse_code(code: str) -> tuple[int, int, int]:
    """(aisle, bay, level) of a bin code such as C-07-2; aisle A is 0."""
    m = CODE.match(code) if isinstance(code, str) else None
    if not m:
        raise BinError(f"bad bin code {code!r}")
    bay = int(m.group(2))
    if bay == 0:
        raise BinError(f"bad bin code {code!r}: bays start at 01")
    return ord(m.group(1)) - ord("A"), bay, int(m.group(3))


def distance(origin: str, code: str) -> int:
    """Walking cost from origin to a bin (bins.md 3.1)."""
    a1, b1, _ = parse_code(origin)
    a2, b2, level = parse_code(code)
    return 4 * abs(a1 - a2) + 2 * abs(b1 - b2) + 3 * (level - 1)


@dataclass(frozen=True)
class Bin:
    code: str
    dims_mm: tuple[int, int, int]
    max_kg: int
    zones: frozenset

    def fits(self, item: Item, qty: int, max_fill: float) -> bool:
        if item.weight_g * qty > self.max_kg * 1000:
            return False
        if any(i > b for i, b in zip(sorted(item.dims_mm), sorted(self.dims_mm))):
            return False
        l, w, h = item.dims_mm
        bl, bw, bh = self.dims_mm
        return l * w * h * qty <= bl * bw * bh * max_fill


class Layout:
    def __init__(self, bins=()):
        self._bins: dict[str, Bin] = {}
        for b in bins:
            self.add(b)

    def add(self, b: Bin) -> None:
        parse_code(b.code)
        old = self._bins.get(b.code)
        if old is None:
            self._bins[b.code] = b
        elif (old.dims_mm, old.max_kg) != (b.dims_mm, b.max_kg):
            raise BinError(f"bin {b.code} is listed twice with different sizes")
        else:
            self._bins[b.code] = Bin(b.code, b.dims_mm, b.max_kg, old.zones | b.zones)

    def __iter__(self):
        return iter(self._bins.values())

    def __len__(self) -> int:
        return len(self._bins)

    def get(self, code: str) -> Bin:
        try:
            return self._bins[code]
        except KeyError:
            raise BinError(f"unknown bin {code}") from None

    def in_zone(self, zone: str) -> list[Bin]:
        return [b for b in self._bins.values() if zone in b.zones]

    @classmethod
    def from_records(cls, records: list) -> "Layout":
        out = cls()
        for rec in records:
            try:
                dims = tuple(int(d) for d in rec["dims_mm"])
                if len(dims) != 3 or min(dims) <= 0:
                    raise ValueError
                out.add(Bin(rec["code"], dims, int(rec["max_kg"]), frozenset(rec.get("zones", ["ambient"]))))
            except (KeyError, TypeError, ValueError):
                raise BinError(f"bad bin record {rec!r}") from None
        return out

    @classmethod
    def load(cls, path: Path) -> "Layout":
        return cls.from_records(json.loads(Path(path).read_text(encoding="utf-8"))["bins"])


def choose_bin(item: Item, layout: Layout, settings: dict, qty: int = 1, occupied=frozenset()) -> str:
    """The bin a pallet of qty units of item goes to (bins.md 3)."""
    origin = settings["putaway"]["origin"]
    max_fill = settings["putaway"]["max_fill"]
    pool = layout.in_zone(item.zone) if item.zone else list(layout)
    candidates = {b.code for b in pool if b.code not in occupied and b.fits(item, qty, max_fill)}
    if not candidates:
        raise NoBinError(f"no free bin for {qty} x {item.sku}")
    return min(candidates, key=lambda code: (distance(origin, code), code))


def putaway(lines, catalog, layout: Layout, settings: dict, occupied=()) -> list[tuple[str, int, str]]:
    """Bins for the pallets of a receipt, in receipt order: (sku, qty, bin) per pallet.

    A line of n units becomes ceil(n / case_qty) pallets of at most case_qty
    units; each pallet takes its own bin.
    """
    taken = set(occupied)
    plan = []
    for sku, qty in lines:
        item = catalog.get(sku)
        left = qty
        while left > 0:
            n = min(left, item.case_qty)
            code = choose_bin(item, layout, settings, n, frozenset(taken))
            taken.add(code)
            plan.append((sku, n, code))
            left -= n
    return plan
