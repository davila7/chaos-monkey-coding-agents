"""Event files (events.md section 3)."""

import re
from dataclasses import dataclass
from datetime import datetime

from ..errors import EventError, ZoneError
from ..rules.parse import Rule, parse
from ..timefmt import parse_local
from ..zones import Zone

UID = re.compile(r"EV-\d{4,}")


@dataclass(frozen=True)
class Override:
    recurrence_id: datetime
    start: datetime | None
    duration: int | None
    cancelled: bool


@dataclass(frozen=True)
class Event:
    uid: str
    summary: str
    zone: Zone
    start: datetime
    duration: int
    rule: Rule | None
    rdates: tuple[datetime, ...]
    exdates: frozenset[datetime]
    overrides: dict[datetime, Override]


def _duration(value, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 7 * 24 * 60:
        raise EventError(f"{where}: duration_min must be a whole number from 1 to 10080")
    return value


def _times(raw, key: str) -> list[datetime]:
    value = raw.get(key, [])
    if not isinstance(value, list):
        raise EventError(f"{key} is not a list")
    return [parse_local(v) for v in value]


def _override(item) -> Override:
    if not isinstance(item, dict) or "recurrence_id" not in item:
        raise EventError(f"override without recurrence_id: {item!r}")
    rid = parse_local(item["recurrence_id"])
    cancelled = item.get("cancelled", False)
    if not isinstance(cancelled, bool):
        raise EventError(f"override {item['recurrence_id']}: cancelled is not true or false")
    if cancelled:
        if "start" in item or "duration_min" in item:
            raise EventError(f"override {item['recurrence_id']}: a cancelled instance has no start or duration")
        return Override(rid, None, None, True)
    start = parse_local(item["start"]) if "start" in item else None
    duration = _duration(item["duration_min"], f"override {item['recurrence_id']}") if "duration_min" in item else None
    if start is None and duration is None:
        raise EventError(f"override {item['recurrence_id']}: changes nothing")
    return Override(rid, start, duration, False)


def load(raw, zones: dict[str, Zone]) -> Event:
    if not isinstance(raw, dict):
        raise EventError("event file is not an object")
    for key in ("uid", "zone", "start", "duration_min"):
        if key not in raw:
            raise EventError(f"missing {key}")
    uid = raw["uid"]
    if not isinstance(uid, str) or not UID.fullmatch(uid):
        raise EventError(f"not an event uid: {uid!r}")
    zone = zones.get(raw["zone"])
    if zone is None:
        raise ZoneError(f"unknown zone: {raw['zone']!r}")
    rule = parse(raw["rrule"]) if raw.get("rrule") is not None else None
    overrides = {}
    for item in raw.get("overrides", []) or []:
        o = _override(item)
        if o.recurrence_id in overrides:
            raise EventError(f"two overrides for {item['recurrence_id']}")
        overrides[o.recurrence_id] = o
    return Event(
        uid=uid,
        summary=str(raw.get("summary", "")),
        zone=zone,
        start=parse_local(raw["start"]),
        duration=_duration(raw["duration_min"], uid),
        rule=rule,
        rdates=tuple(_times(raw, "rdate")),
        exdates=frozenset(_times(raw, "exdate")),
        overrides=overrides,
    )
