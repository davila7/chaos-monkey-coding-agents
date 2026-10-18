"""Stations, constituents and predicted events."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Constituent:
    name: str
    amplitude: float  # metres
    phase: float  # degrees, local epoch


@dataclass(frozen=True)
class Station:
    id: str
    name: str
    region: str
    lat: float
    lon: float
    utc_offset_minutes: int
    z0: float  # mean sea level above chart datum, metres
    constituents: tuple = ()

    def constituent(self, name: str) -> Constituent | None:
        for c in self.constituents:
            if c.name == name:
                return c
        return None


@dataclass(frozen=True)
class Event:
    kind: str  # "high" or "low"
    time: datetime  # station local time
    height: float


@dataclass(frozen=True)
class Sample:
    time: datetime
    height: float
