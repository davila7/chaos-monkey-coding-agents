"""Time zones defined by data/zones.json: a standard offset and an optional
daylight saving period with yearly start and end rules."""

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from .errors import ZoneError

WEEKDAYS = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")


@dataclass(frozen=True)
class Transition:
    month: int
    week: str  # "1".."4" or "last"
    weekday: str
    time: str  # HH:MM
    basis: str  # "utc" or "wall"

    def day(self, year: int) -> date:
        wd = WEEKDAYS.index(self.weekday)
        if self.week == "last":
            nxt = date(year + (self.month == 12), self.month % 12 + 1, 1)
            d = nxt - timedelta(days=1)
            while d.weekday() != wd:
                d -= timedelta(days=1)
            return d
        d = date(year, self.month, 1)
        while d.weekday() != wd:
            d += timedelta(days=1)
        return d + timedelta(weeks=int(self.week) - 1)

    def instant(self, year: int, offset_before: int) -> datetime:
        """The UTC instant of the change, as a naive datetime."""
        h, m = map(int, self.time.split(":"))
        local = datetime.combine(self.day(year), datetime.min.time()) + timedelta(hours=h, minutes=m)
        if self.basis == "utc":
            return local
        return local - timedelta(minutes=offset_before)


@dataclass(frozen=True)
class Zone:
    name: str
    std: int
    dst: int | None = None
    start: Transition | None = None
    end: Transition | None = None

    def dst_span(self, year: int) -> tuple[datetime, datetime] | None:
        if self.dst is None:
            return None
        return self.start.instant(year, self.std), self.end.instant(year, self.dst)

    def offset_at(self, utc: datetime) -> int:
        span = self.dst_span(utc.year)
        if span is None:
            return self.std
        start, end = span
        # South of the equator daylight saving starts late in the year and
        # ends early in the next one.
        if start <= end:
            inside = start <= utc < end
        else:
            inside = utc >= start or utc < end
        return self.dst if inside else self.std

    def to_utc(self, local: datetime) -> datetime:
        """A local wall time as UTC (zones.md section 4)."""
        if self.dst is None:
            return local - timedelta(minutes=self.std)
        candidates = [local - timedelta(minutes=o) for o in (self.dst, self.std)]
        valid = [u for u, o in zip(candidates, (self.dst, self.std)) if self.offset_at(u) == o]
        if valid:
            return min(valid)
        return local - timedelta(minutes=self.std)

    def to_local(self, utc: datetime) -> datetime:
        return utc + timedelta(minutes=self.offset_at(utc))


_TIME = re.compile(r"([01]\d|2[0-3]):[0-5]\d")


def _transition(raw) -> Transition:
    if not isinstance(raw, dict):
        raise ZoneError(f"not a transition: {raw!r}")
    try:
        t = Transition(int(raw["month"]), str(raw["week"]), raw["weekday"], raw["time"], raw.get("basis", "wall"))
    except (KeyError, TypeError, ValueError):
        raise ZoneError(f"not a transition: {raw!r}") from None
    if not 1 <= t.month <= 12 or t.week not in ("1", "2", "3", "4", "last") or t.weekday not in WEEKDAYS:
        raise ZoneError(f"not a transition: {raw!r}")
    if not isinstance(t.time, str) or not _TIME.fullmatch(t.time) or t.basis not in ("utc", "wall"):
        raise ZoneError(f"not a transition: {raw!r}")
    return t


def _offset(value) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not -720 <= value <= 840:
        raise ZoneError(f"not an offset in minutes: {value!r}")
    return value


def load(raw: dict) -> dict[str, Zone]:
    zones = {}
    for name, z in raw.items():
        if not isinstance(z, dict):
            raise ZoneError(f"zone {name}: not an object")
        std = _offset(z.get("std_offset_min"))
        dst = z.get("dst")
        if dst is None:
            zones[name] = Zone(name, std)
            continue
        if not isinstance(dst, dict):
            raise ZoneError(f"zone {name}: dst is not an object")
        offset = _offset(dst.get("offset_min"))
        if offset == std:
            raise ZoneError(f"zone {name}: daylight saving offset equals the standard offset")
        zones[name] = Zone(name, std, offset, _transition(dst.get("start")), _transition(dst.get("end")))
    return zones
