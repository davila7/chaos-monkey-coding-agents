"""Weights and lengths. The package keeps grams and millimetres; other units
appear only at the edges (docs/settings.md 3)."""

from decimal import ROUND_HALF_EVEN, Decimal

from .errors import SettingsError

GRAMS = {"g": Decimal(1), "kg": Decimal(1000), "lb": Decimal("453.59237"), "oz": Decimal("28.349523125")}
MILLIMETRES = {"mm": Decimal(1), "cm": Decimal(10), "m": Decimal(1000), "in": Decimal("25.4")}


def _quantum(places: int) -> Decimal:
    return Decimal(1).scaleb(-places)


def _factor(table: dict, unit: str) -> Decimal:
    try:
        return table[unit]
    except KeyError:
        raise SettingsError(f"unknown unit {unit!r}") from None


def convert_weight(value, from_unit: str, to_unit: str, places: int) -> Decimal:
    """value in from_unit, expressed in to_unit and rounded half to even."""
    grams = Decimal(str(value)) * _factor(GRAMS, from_unit)
    return (grams / _factor(GRAMS, to_unit)).quantize(_quantum(places), rounding=ROUND_HALF_EVEN)


def convert_length(value, from_unit: str, to_unit: str, places: int) -> Decimal:
    mm = Decimal(str(value)) * _factor(MILLIMETRES, from_unit)
    return (mm / _factor(MILLIMETRES, to_unit)).quantize(_quantum(places), rounding=ROUND_HALF_EVEN)


def to_grams(value, unit: str) -> int:
    """A weight in whole grams, rounded half to even."""
    return int(convert_weight(value, unit, "g", 0))


def weight(grams: int, settings: dict) -> Decimal:
    return convert_weight(grams, "g", settings["weight_unit"], settings["rounding"]["weight"])


def length(mm: int, settings: dict) -> Decimal:
    return convert_length(mm, "mm", settings["length_unit"], settings["rounding"]["length"])


def format_weight(grams: int, settings: dict) -> str:
    return f"{weight(grams, settings)} {settings['weight_unit']}"


def format_dims(dims_mm: tuple[int, int, int], settings: dict) -> str:
    unit = settings["length_unit"]
    return " x ".join(str(length(d, settings)) for d in dims_mm) + f" {unit}"


def volume_litres(dims_mm: tuple[int, int, int]) -> Decimal:
    l, w, h = dims_mm
    return (Decimal(l) * w * h / Decimal(1_000_000)).quantize(Decimal("0.001"), rounding=ROUND_HALF_EVEN)
