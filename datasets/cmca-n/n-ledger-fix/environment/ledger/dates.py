from datetime import date


def parse_date(text: str) -> date:
    """Accepts ISO dates (2026-01-31) and day-first dates (31/01/2026)."""
    s = text.strip()
    if "-" in s:
        y, m, d = (int(p) for p in s.split("-"))
        return date(y, m, d)
    first, second, year = (int(p) for p in s.split("/"))
    return date(year, first, second)


def month_key(d: date) -> str:
    return f"{d.year}-{d.month:02d}"
