"""Parsing recurrence rules (rules.md sections 2 and 3)."""

import re
from dataclasses import dataclass, field
from datetime import date, datetime

from ..errors import RuleError
from ..timefmt import parse_until
from ..zones import WEEKDAYS

FREQS = ("DAILY", "WEEKLY", "MONTHLY", "YEARLY")
_PARTS = ("FREQ", "INTERVAL", "COUNT", "UNTIL", "BYDAY", "BYMONTHDAY", "BYMONTH", "BYSETPOS", "WKST")
_BYDAY = re.compile(r"([+-]?)(\d{1,2})?(MO|TU|WE|TH|FR|SA|SU)")
_INT = re.compile(r"[+-]?\d+")


@dataclass(frozen=True)
class Rule:
    freq: str
    interval: int = 1
    count: int | None = None
    until: tuple[str, datetime | date] | None = None
    byday: tuple[tuple[int, int], ...] = ()  # (ordinal or 0, weekday index)
    bymonthday: tuple[int, ...] = ()
    bymonth: tuple[int, ...] = ()
    bysetpos: tuple[int, ...] = ()
    wkst: int = 0
    text: str = field(default="", compare=False)


def _ints(name: str, value: str, low: int, high: int, signed: bool) -> tuple[int, ...]:
    out = []
    for item in value.split(","):
        if not _INT.fullmatch(item):
            raise RuleError(f"{name}: not a number: {item!r}")
        n = int(item)
        if n == 0 or abs(n) < low or abs(n) > high or (n < 0 and not signed):
            raise RuleError(f"{name}: out of range: {item}")
        out.append(n)
    if len(set(out)) != len(out):
        raise RuleError(f"{name}: repeated value")
    return tuple(out)


def _days(value: str) -> tuple[tuple[int, int], ...]:
    out = []
    for item in value.split(","):
        m = _BYDAY.fullmatch(item)
        if not m:
            raise RuleError(f"BYDAY: not a weekday: {item!r}")
        sign, num, day = m.groups()
        if num is None:
            if sign:
                raise RuleError(f"BYDAY: sign without a number: {item!r}")
            n = 0
        else:
            n = int(num)
            if not 1 <= n <= 53:
                raise RuleError(f"BYDAY: out of range: {item}")
            if sign == "-":
                n = -n
        out.append((n, WEEKDAYS.index(day)))
    if len(set(out)) != len(out):
        raise RuleError("BYDAY: repeated value")
    return tuple(out)


def parse(text) -> Rule:
    if not isinstance(text, str) or not text:
        raise RuleError(f"not a rule: {text!r}")
    parts = {}
    for item in text.split(";"):
        name, sep, value = item.partition("=")
        if not sep or not value:
            raise RuleError(f"not NAME=VALUE: {item!r}")
        if name not in _PARTS:
            raise RuleError(f"unsupported part: {name}")
        if name in parts:
            raise RuleError(f"part given twice: {name}")
        parts[name] = value
    freq = parts.get("FREQ")
    if freq not in FREQS:
        raise RuleError(f"FREQ missing or unsupported: {freq!r}")
    if "COUNT" in parts and "UNTIL" in parts:
        raise RuleError("COUNT and UNTIL together")
    kw = {"freq": freq, "text": text}
    if "INTERVAL" in parts:
        (kw["interval"],) = _ints("INTERVAL", parts["INTERVAL"], 1, 1000, False)
    if "COUNT" in parts:
        (kw["count"],) = _ints("COUNT", parts["COUNT"], 1, 10000, False)
    if "UNTIL" in parts:
        kw["until"] = parse_until(parts["UNTIL"])
    if "BYDAY" in parts:
        kw["byday"] = _days(parts["BYDAY"])
    if "BYMONTHDAY" in parts:
        kw["bymonthday"] = _ints("BYMONTHDAY", parts["BYMONTHDAY"], 1, 31, True)
    if "BYMONTH" in parts:
        kw["bymonth"] = _ints("BYMONTH", parts["BYMONTH"], 1, 12, False)
    if "BYSETPOS" in parts:
        kw["bysetpos"] = _ints("BYSETPOS", parts["BYSETPOS"], 1, 366, True)
    if "WKST" in parts:
        if parts["WKST"] not in WEEKDAYS:
            raise RuleError(f"WKST: not a weekday: {parts['WKST']!r}")
        kw["wkst"] = WEEKDAYS.index(parts["WKST"])
    rule = Rule(**kw)
    _check(rule)
    return rule


def _check(rule: Rule) -> None:
    ordinals = [n for n, _ in rule.byday if n]
    if rule.bymonthday and rule.freq == "WEEKLY":
        raise RuleError("BYMONTHDAY with FREQ=WEEKLY")
    if ordinals and rule.freq in ("DAILY", "WEEKLY"):
        raise RuleError(f"BYDAY with a number and FREQ={rule.freq}")
    if ordinals and rule.freq == "YEARLY" and not rule.bymonth:
        raise RuleError("BYDAY with a number and FREQ=YEARLY needs BYMONTH")
    if ordinals and any(abs(n) > 5 for n in ordinals):
        raise RuleError("BYDAY: a month has at most five of each weekday")
    if rule.bysetpos:
        if rule.freq not in ("MONTHLY", "YEARLY"):
            raise RuleError(f"BYSETPOS with FREQ={rule.freq}")
        if not (rule.byday or rule.bymonthday):
            raise RuleError("BYSETPOS needs BYDAY or BYMONTHDAY")
