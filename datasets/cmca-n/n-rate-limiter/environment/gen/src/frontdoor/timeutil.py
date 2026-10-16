"""Trace timestamps: `YYYY-MM-DDTHH:MM:SS.mmmZ` <-> integer milliseconds since the Unix epoch."""

import calendar
import re
import time

_TS = re.compile(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})\.(\d{3})Z")


def parse_ts(text: str) -> int:
    m = _TS.fullmatch(text)
    if not m:
        raise ValueError(f"not a trace timestamp: {text!r}")
    y, mo, d, h, mi, s, ms = (int(g) for g in m.groups())
    if not (1 <= mo <= 12 and 1 <= d <= 31 and h < 24 and mi < 60 and s < 60):
        raise ValueError(f"not a trace timestamp: {text!r}")
    return calendar.timegm((y, mo, d, h, mi, s, 0, 0, 0)) * 1000 + ms


def format_ts(ms: int) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(ms // 1000)) + f".{ms % 1000:03d}Z"
