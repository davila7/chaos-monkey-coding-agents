"""Number formatting for the report command (docs/commands.md, report).

The report layouts were designed for locales that group digits by thousands,
so this module groups the integer part in threes with the locale's group
separator and uses the locale's decimal separator. It writes negative numbers
with an ASCII hyphen.
"""

from decimal import Decimal

from tally.fmt.locales import Locale


def group_thousands(digits: str, sep: str) -> str:
    out = []
    while len(digits) > 3:
        out.append(digits[-3:])
        digits = digits[:-3]
    out.append(digits)
    return sep.join(reversed(out))


def format_number(value, locale: Locale | None, places: int = 0) -> str:
    """int or Decimal -> display text with `places` fraction digits."""
    if value is None:
        return ""
    d = Decimal(value)
    text = f"{abs(d):.{places}f}"
    whole, _, frac = text.partition(".")
    if locale is None:
        body = whole + ("." + frac if frac else "")
    else:
        body = group_thousands(whole, locale.group) + (locale.decimal + frac if frac else "")
    return ("-" if d < 0 else "") + body
