"""Conversion to and from SI units (quantities.md sections 4 and 5)."""

from fractions import Fraction

from .dims import Dimension
from .errors import DimensionError


def to_si(value: Fraction, unit) -> Fraction:
    if unit.kind == "absolute":
        return (value + unit.offset) * unit.factor
    return value * unit.factor


def from_si(si: Fraction, unit) -> Fraction:
    if unit.kind == "absolute":
        return si / unit.factor - unit.offset
    return si / unit.factor


def express(si: Fraction, kind: str, dim: Dimension, target) -> Fraction:
    """The value of an SI quantity of the given kind in the target unit."""
    if target.dim != dim:
        raise DimensionError(f"{dim.text()} cannot be written in {target.text} ({target.dim.text()})")
    if kind == "absolute" and target.kind == "difference":
        raise DimensionError(f"an absolute temperature cannot be written in {target.text}")
    if kind == "difference" and target.kind == "absolute":
        raise DimensionError(f"a temperature difference cannot be written in {target.text}")
    if kind == "difference":
        return si / target.factor
    return from_si(si, target)
