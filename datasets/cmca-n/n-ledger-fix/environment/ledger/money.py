"""Amounts are integer minor units (cents) tagged with an ISO currency code."""
from dataclasses import dataclass

from ledger.convert import round_cents, to_base


@dataclass(frozen=True)
class Money:
    cents: int
    currency: str

    def __neg__(self) -> "Money":
        return Money(-self.cents, self.currency)

    def in_base(self, rate: str) -> int:
        return round_cents(to_base(self, rate))


def parse_amount(text: str, decimal: str = ".") -> int:
    """Parses "980", "2450.5", "1,200.00", "-7.25" or an accounting negative "(3.40)" into cents.

    With decimal="," the roles of "." and "," swap: "1.200,5" is 1200.50.
    """
    s = text.strip()
    negative = s.startswith("(") and s.endswith(")")
    if negative:
        s = s[1:-1]
    if decimal == ",":
        s = s.replace(",", ".")
    s = s.replace(",", "")
    whole, _, frac = s.partition(".")
    cents = int(whole or "0") * 100 + int(frac or "0")
    return cents
