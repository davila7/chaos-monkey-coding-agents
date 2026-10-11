# Ledger conventions

These rules define how the `ledger` package reads statements and builds monthly reports. Where a code comment disagrees with this note, this note is correct.

## Statements

A statement is a CSV file under `data/statements/`. It starts with `#key: value` header lines:

- `account` and `currency` (ISO code) are required.
- `delimiter` is the field separator; `,` when absent.
- `decimal` is the decimal separator; `.` when absent. When it is `,`, the group separator is `.`.
- `date_order` is `ymd` (2026-01-31, used when absent), `dmy` (31/01/2026) or `mdy` (01/31/2026).

The columns are `id`, `date`, `description`, `amount` and `reverses`.

## Amounts

Amounts are stored as integer cents. A negative amount is written either with a leading minus (`-7.25`) or in parentheses (`(7.25)`). One or two fraction digits are allowed; `2450.5` is 245050 cents. Group separators are ignored. Anything else, including more than two fraction digits, raises `FormatError`. An invalid date also raises `FormatError`.

## Conversion and rounding

Reports are in USD. `data/rates.csv` gives, for each month, how many USD one unit of a currency was worth. An entry is converted at the rate of the month that applies to it (see Reversals).

Each entry is converted on its own with exact decimal arithmetic and rounded to whole cents before it is added to any total. Rounding is half away from zero: 1618.5 cents becomes 1619 and -1258.5 becomes -1259. Month totals are sums of rounded entries, and the report total is the sum of the month totals.

## Reversals

An entry whose `reverses` column names another entry of the same statement cancels it. The reversal must carry exactly the negated amount of the original, and the original must itself be a regular entry; otherwise `UnmatchedReversal` is raised. A reversal that names an id not in the statement also raises `UnmatchedReversal`.

A reversal is booked in the month of the original entry, not the month in which it was posted, and it is converted at the original entry's rate. A matched pair therefore nets to exactly zero in USD.
