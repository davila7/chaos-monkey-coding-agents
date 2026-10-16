"""Harmonic synthesis of the water level."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from tidecalc.astro import constituents, equilibrium, nodal
from tidecalc.model import Sample, Station


class Synthesizer:
    """Water level at a station. Equilibrium arguments and nodal factors are
    taken once at the start of the span, which is accurate to a few
    centimetres over a month."""

    def __init__(self, station: Station, start: datetime):
        self.station = station
        self.start = start
        utc = start.astimezone(timezone.utc)
        self.terms = []
        for c in station.constituents:
            if not constituents.known(c.name):
                continue
            f, u = nodal.factors(c.name, utc)
            phase0 = equilibrium.v0(c.name, utc) + u - c.phase
            self.terms.append((f * c.amplitude, math.radians(constituents.speed(c.name)), math.radians(phase0)))

    def height(self, t: datetime) -> float:
        hours = (t - self.start).total_seconds() / 3600.0
        return self.station.z0 + sum(a * math.cos(w * hours + p) for a, w, p in self.terms)

    def series(self, hours: float, step_minutes: int) -> list:
        out = []
        steps = int(hours * 60 // step_minutes)
        for i in range(steps + 1):
            t = self.start + timedelta(minutes=i * step_minutes)
            out.append(Sample(t, self.height(t)))
        return out
