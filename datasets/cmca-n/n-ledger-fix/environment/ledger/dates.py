from datetime import date

ORDERS = ("ymd", "dmy", "mdy")


def parse_date(text: str, order: str = "ymd") -> date:
    """Parses 2026-01-31 (ymd), 31/01/2026 (dmy) or 01/31/2026 (mdy)."""
    s = text.strip()
    if order == "ymd":
        y, m, d = (int(p) for p in s.split("-"))
        return date(y, m, d)
    first, second, year = (int(p) for p in s.split("/"))
    return date(year, first, second)


def month_key(d: date) -> str:
    return f"{d.year}-{d.month:02d}"
