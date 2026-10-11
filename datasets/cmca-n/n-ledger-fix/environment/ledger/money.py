"""Amounts are stored as integer cents."""


def parse_amount(text: str) -> int:
    """Parses "12.50", "12.5", "980" or an accounting negative "(3.40)" into cents."""
    s = text.strip().replace(",", "")
    negative = s.startswith("(") and s.endswith(")")
    if negative:
        s = s[1:-1]
    whole, _, frac = s.partition(".")
    cents = int(whole or "0") * 100 + int(frac or "0")
    return cents


def format_cents(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}{cents // 100}.{cents % 100:02d}"
