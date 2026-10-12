"""Conversion of amounts into the base currency."""
from ledger.money import Money
from ledger.rates import BASE


def to_base(amount: Money, rate: str) -> float:
    """Base-currency value of amount, in cents, before rounding."""
    if amount.currency == BASE:
        return float(amount.cents)
    return amount.cents * float(rate)


def round_cents(value: float) -> int:
    # Round half to even, so that rounding errors cancel out over a month.
    return round(value)
