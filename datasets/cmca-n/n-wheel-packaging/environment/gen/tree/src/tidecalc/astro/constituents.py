"""Tidal constituents: angular speeds and the Doodson-style arguments used to
compute their equilibrium phase."""

from __future__ import annotations

# Speed in degrees per mean solar hour.
SPEEDS = {
    "M2": 28.9841042,
    "S2": 30.0,
    "N2": 28.4397295,
    "K2": 30.0821373,
    "K1": 15.0410686,
    "O1": 13.9430356,
    "P1": 14.9589314,
    "Q1": 13.3986609,
    "M4": 57.9682084,
    "MS4": 58.9841042,
    "M6": 86.9523127,
    "SA": 0.0410686,
    "SSA": 0.0821373,
}

# Multiples of (T, s, h, p) and a constant in degrees: V0 = a*T + b*s + c*h + d*p + e,
# where T is the hour angle of the mean sun plus 180 degrees.
ARGUMENTS = {
    "M2": (2, -2, 2, 0, 0),
    "S2": (2, 0, 0, 0, 0),
    "N2": (2, -3, 2, 1, 0),
    "K2": (2, 0, 2, 0, 0),
    "K1": (1, 0, 1, 0, 90),
    "O1": (1, -2, 1, 0, -90),
    "P1": (1, 0, -1, 0, -90),
    "Q1": (1, -3, 1, 1, -90),
    "M4": (4, -4, 4, 0, 0),
    "MS4": (4, -2, 2, 0, 0),
    "M6": (6, -6, 6, 0, 0),
    "SA": (0, 0, 1, 0, 0),
    "SSA": (0, 0, 2, 0, 0),
}


def known(name: str) -> bool:
    return name in SPEEDS


def speed(name: str) -> float:
    try:
        return SPEEDS[name]
    except KeyError:
        raise KeyError(f"unknown constituent {name!r}") from None
