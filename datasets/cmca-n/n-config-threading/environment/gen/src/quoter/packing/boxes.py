"""Box catalogues. A parcel is shipped in the smallest box it fits."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from quoter import settings


@dataclass(frozen=True)
class Box:
    code: str
    dims: tuple
    tare_kg: Decimal


def _box(code: str, l: int, w: int, h: int, tare: str) -> Box:
    return Box(code, (Decimal(l), Decimal(w), Decimal(h)), Decimal(tare))


BOX_SETS = {
    "standard": (
        _box("S1", 22, 16, 8, "0.10"),
        _box("S2", 30, 22, 12, "0.18"),
        _box("M1", 40, 30, 20, "0.32"),
        _box("M2", 50, 40, 30, "0.55"),
        _box("L1", 60, 40, 40, "0.80"),
        _box("L2", 80, 60, 40, "1.20"),
        _box("XL", 120, 80, 60, "2.40"),
    ),
    "eco": (
        _box("E1", 25, 20, 10, "0.08"),
        _box("E2", 40, 30, 25, "0.25"),
        _box("E3", 60, 50, 40, "0.60"),
    ),
    "none": (),
}


def catalogue() -> tuple:
    return BOX_SETS[settings.SETTINGS.box_set]
