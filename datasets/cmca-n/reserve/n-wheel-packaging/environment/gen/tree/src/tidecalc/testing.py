"""Helpers for code that uses tidecalc in its own tests.

    from tidecalc.testing import make_station, assert_events_close
"""

from __future__ import annotations

from tidecalc.model import Constituent, Station

SEMIDIURNAL = (("M2", 1.0, 0.0), ("S2", 0.3, 30.0))


def make_station(ident: str = "st-test", constituents=SEMIDIURNAL, z0: float = 2.0, utc_offset_minutes: int = 0) -> Station:
    """A station that is not in the catalogue, for tests."""
    cons = tuple(Constituent(n, float(a), float(p)) for n, a, p in constituents)
    return Station(ident, f"Test {ident}", "test", 0.0, 0.0, utc_offset_minutes, z0, cons)


def assert_events_close(actual, expected, minutes: float = 2.0, metres: float = 0.01) -> None:
    """Raise AssertionError unless both event lists match within tolerances."""
    if len(actual) != len(expected):
        raise AssertionError(f"{len(actual)} events, expected {len(expected)}")
    for a, e in zip(actual, expected):
        if a.kind != e.kind:
            raise AssertionError(f"{a.kind} at {a.time}, expected {e.kind}")
        if abs((a.time - e.time).total_seconds()) > minutes * 60:
            raise AssertionError(f"{a.kind} at {a.time}, expected {e.time}")
        if abs(a.height - e.height) > metres:
            raise AssertionError(f"height {a.height:.3f}, expected {e.height:.3f}")
