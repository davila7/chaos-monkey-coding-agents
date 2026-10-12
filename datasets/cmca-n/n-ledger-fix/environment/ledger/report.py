from ledger.convert import round_cents, to_base
from ledger.dates import month_key
from ledger.money import Money
from ledger.rates import BASE, Rates
from ledger.reversals import bookings
from ledger.statement import Statement


def build_report(statement: Statement, rates: Rates) -> dict:
    sums: dict[str, float] = {}
    for b in bookings(statement.entries):
        rate = rates.rate(statement.currency, month_key(b.rate_date))
        key = month_key(b.entry.date)
        sums[key] = sums.get(key, 0) + to_base(Money(b.entry.cents, statement.currency), rate)
    months = {key: round_cents(value) for key, value in sorted(sums.items())}
    return {
        "account": statement.account,
        "currency": statement.currency,
        "base": BASE,
        "months": months,
        "total": sum(months.values()),
    }
