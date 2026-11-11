"""Member numbers (docs/data.md, section 1)."""

import re

_ID = re.compile(r"\s*[Mm]-(\d{1,6})\s*\Z")


def number(text: str) -> int | None:
    """The number of a member id as people type it (`M-0042`, `M-42`, `m-42`), or None."""
    m = _ID.match(text)
    return int(m.group(1)) if m else None


def fmt(n: int) -> str:
    return f"M-{n:04d}"
