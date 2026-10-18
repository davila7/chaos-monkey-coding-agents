"""Mean astronomical longitudes and equilibrium arguments."""

from __future__ import annotations

from datetime import datetime, timezone

from tidecalc.astro.constituents import ARGUMENTS

EPOCH = datetime(2000, 1, 1, 12, tzinfo=timezone.utc)


def _centuries(t: datetime) -> float:
    return (t - EPOCH).total_seconds() / 86400.0 / 36525.0


def longitudes(t: datetime) -> dict:
    """Mean longitudes in degrees at UTC time t: s (moon), h (sun), p (lunar
    perigee), N (lunar node)."""
    c = _centuries(t)
    return {
        "s": (218.3164477 + 481267.88123421 * c) % 360.0,
        "h": (280.4664567 + 36000.76982779 * c) % 360.0,
        "p": (83.3532465 + 4069.0137287 * c) % 360.0,
        "N": (125.0445479 - 1934.1362891 * c) % 360.0,
    }


def v0(name: str, t: datetime) -> float:
    """Equilibrium argument of a constituent at UTC time t, degrees."""
    lon = longitudes(t)
    hours = t.hour + t.minute / 60.0 + t.second / 3600.0
    big_t = (15.0 * hours + 180.0) % 360.0
    a, b, c, d, e = ARGUMENTS[name]
    return (a * big_t + b * lon["s"] + c * lon["h"] + d * lon["p"] + e) % 360.0
