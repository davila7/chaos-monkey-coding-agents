# Ledger conventions

This note is the reference for how the `ledger` package reads statements, values them in US dollars and builds its reports. The package code, its docstrings and its comments are meant to agree with it. Where a docstring or code comment disagrees with this note, this note is correct and the code is wrong.

Contents:

1. Package layout
2. Statements
3. Dialects and layout
4. Amounts
5. Dates, months and fiscal periods
6. Exchange rates
7. Conversion and rounding
8. Reversals
9. Categories and accounts
10. Tax
11. Reports
12. Rendering
13. Auxiliary files
14. Command line
15. Errors

## 1. Package layout

The package is split into sub-packages that depend on each other in one direction only, from the bottom of this list to the top:

| Sub-package | Holds |
|---|---|
| `ledger.core` | `Money`, currency table, decimal parsing, rounding, id helpers |
| `ledger.periods` | month keys, fiscal years, ISO weeks, business-day calendars, closed periods |
| `ledger.parse` | header lines, dialects, amounts, dates, statement reading and writing, other file formats |
| `ledger.fx` | rate files, the rate table, rate lookup, conversion, cross rates, revaluation |
| `ledger.book` | entries, reversals and booking dates, chart of accounts, journal, transfers, splits, rules, audit |
| `ledger.tax` | tax rules by jurisdiction and date, tax portions, returns, schedules |
| `ledger.report` | monthly, tax, balance, trial balance, category, comparison and other reports |
| `ledger.render` | text, CSV, Markdown, HTML and JSON output |
| `ledger.cli` | the `python -m ledger` command line |

Modules whose names start with an underscore (`_currency_table`, `_dialect_table`, `_chart`, `_rule_table`, `_merchant_table`, `_holiday_table`) hold data tables. They are part of the package and are read at import time.

The base currency is the US dollar (`ledger.BASE_CURRENCY`). Every report value is an integer number of US cents.

## 2. Statements

### 2.1 File structure

A statement is a text file in UTF-8. A leading byte order mark is ignored. The file has three parts, in this order:

1. Header lines. Each starts with `#` and has the form `#key: value`. Keys are case-insensitive and are stored in lower case; values are stripped of surrounding spaces.
2. The column line, which names the columns in the order the rows use them. Blank lines between the header and the column line are ignored.
3. Rows. Blank lines and lines starting with `#` are ignored here too; such a `#` line is a comment, not a header.

Line numbers in error messages are one-based and count every physical line of the file, including header lines and blank lines.

### 2.2 Header keys

| Key | Required | Meaning |
|---|---|---|
| `account` | yes | Name of the account the statement belongs to. Used as the report name. |
| `currency` | yes | ISO 4217 code of the statement currency (case-insensitive). |
| `dialect` | no | Name of a dialect from the dialect table (section 3). |
| `delimiter` | no | Field separator (section 3.2). |
| `decimal` | no | Decimal mark of amounts: `.` or `,`. |
| `date_order` | no | `ymd`, `dmy` or `mdy` (section 5.1). |
| `jurisdiction` | no | Tax jurisdiction code (section 10). Empty means the statement is not taxed. |
| `fiscal_start` | no | Month number 1 to 12 in which the account's fiscal year starts (section 5.3). |
| `opened` | no | Informational; not interpreted. |
| `note` | no | Informational; not interpreted. |

An unknown key, a key that appears twice, or a missing required key is a `HeaderError`.

### 2.3 Columns

The required columns are `id`, `date`, `description` and `amount`. The optional columns are `reverses`, `category` and `tax`. Column names are case-insensitive, and columns may appear in any order. An unknown column name, a repeated name or a missing required column is a `FormatError` on the column line.

Every row must have exactly as many fields as the column line. Fields are stripped of surrounding spaces. Quoting follows the usual CSV rules, so a field that contains the delimiter is written in double quotes.

| Column | Meaning |
|---|---|
| `id` | Entry id, unique within the statement. Ids are compared exactly as written (case-sensitive). |
| `date` | Posting date, in the statement's date order. |
| `description` | Free text. |
| `amount` | Signed amount in the statement currency (section 4). Positive amounts increase the account, negative amounts decrease it. |
| `reverses` | Id of the entry this row cancels, or empty (section 8). |
| `category` | Dotted category path, stored in lower case, or empty (section 9). |
| `tax` | Tax code `S`, `R`, `Z` or `E`, stored in upper case, or empty (section 10). |

An empty id, an id used twice (`DuplicateEntry`) and an entry that reverses itself are errors.

### 2.4 Other formats

`ledger.parse.importers` reads two more formats into the same `Statement`: JSON lines (`.jsonl`) and fixed-width text (`.txt`). Both are converted to CSV text first, so every rule in this note applies to them unchanged. In both formats amounts are strings written in the statement's layout. A `delimiter` header key in these formats is ignored, because the converted text is always comma-delimited.

### 2.5 Writing statements

`ledger.parse.writer.write_statement` writes a statement so that it reads back to the same entries. It writes the dialect name when the statement has one and also every layout key explicitly, so the written file does not depend on the dialect table. Amounts are written without group separators and with a leading minus for negatives.

## 3. Dialects and layout

### 3.1 What a layout is

The layout of a statement is the set of four values that decide how its body is read: `delimiter`, `decimal`, `date_order` and `jurisdiction`. `Statement.layout` holds the layout a statement was read with, and `ledger check` prints it.

### 3.2 Delimiter values

A `delimiter` value is either a name (`comma`, `semicolon`, `pipe`, `tab`, case-insensitive) or a single character that is not a letter, a digit, a quote or `#`. A tab can only be given by name.

### 3.3 Dialects

A dialect records the layout one sender uses for all its statements, so that a header can name the sender (`#dialect: northgate`) instead of spelling each value out. Dialect names are case-insensitive. The table is in `ledger.parse._dialect_table`; an unknown name is `UnknownDialect`.

### 3.4 Which value wins

Each layout key takes its value from the first of these sources that has one:

1. the statement's own header line for that key;
2. the dialect named by the statement's `dialect` header;
3. the base layout: delimiter `,`, decimal `.`, date order `ymd`, no jurisdiction.

A header line therefore always wins over the dialect. This is what lets one sender's statement deviate from its usual layout (an export made with a different setting, or an account held in another jurisdiction) without a new dialect. A dialect only fills the keys the header leaves out.

Example: the `northgate` dialect is semicolon-delimited with a `,` decimal mark, `dmy` dates and jurisdiction `ARD`. A statement with the header lines below is read with delimiter `,`, decimal `.`, `ymd` dates and jurisdiction `ARD`:

    #account: cross-month
    #currency: EUR
    #dialect: northgate
    #delimiter: comma
    #decimal: .
    #date_order: ymd

### 3.5 Checks on a layout

`decimal` must be `.` or `,`; `date_order` must be one of the three orders. The delimiter and the decimal mark must differ, except that a `,` delimiter with a `,` decimal mark is allowed because such amounts are quoted. Violations are `HeaderError`.

### 3.6 Guessing

`ledger.parse.sniff` guesses a layout from a file's body and `ledger check --guess` compares the guess with the layout the file is read with. The guess is advisory: reading always follows section 3.4, never the guess.

## 4. Amounts

### 4.1 Minor units

Amounts are stored as integers in minor units of their currency. The number of minor-unit digits is the currency's exponent from `ledger.core._currency_table`: 2 for most currencies, 0 for currencies such as JPY or KRW, 3 for currencies such as KWD, BHD or TND. So `12.34` EUR is 1234, `1500` JPY is 1500 and `1.5` KWD is 1500.

### 4.2 Accepted forms

An amount consists of, in order:

- an optional sign: a leading `-` or `+`, or surrounding parentheses for a negative amount (`(7.25)` is -725). Spaces inside the parentheses are allowed. A sign inside parentheses, and unbalanced parentheses, are errors;
- a whole part of digits, optionally with group separators;
- optionally, the decimal mark followed by one or more digits, at most as many as the currency's exponent. Fewer digits are padded: `2450.5` is 245050 cents.

The decimal mark is the statement's `decimal` value. The group separator is `,` when the decimal mark is `.`, and `.` when the decimal mark is `,`. A space is also accepted as a group separator. Group separators may only appear in the whole part, and must split it into groups of three digits after a first group of one to three digits (`1,234,567` is fine, `12,34` is not).

Anything else is a `FormatError`: an empty amount, more fraction digits than the exponent allows (`1.234` for EUR, `1.5` for JPY), a decimal mark without digits after it, more than one decimal mark, letters, or a bare sign.

### 4.3 Display

Formatting goes the other way (`ledger.core.money.format_amount`): the whole part, the decimal mark and exactly `exponent` fraction digits, with an optional group separator every three digits. A negative amount is written with a single leading minus sign before its digits and is otherwise written exactly like the positive amount of the same size: -50 cents is `-0.50`, -123456 cents is `-1,234.56` with `,` groups. Zero is never negative. Section 12 says which formats use which separators.

## 5. Dates, months and fiscal periods

### 5.1 Date orders

| Order | Example | Separators |
|---|---|---|
| `ymd` | `2026-01-31` | `-` |
| `dmy` | `31/01/2026`, `31.01.2026` | `/` or `.` |
| `mdy` | `01/31/2026` | `/` |

Years have four digits; day and month have one or two. A date that does not exist (`2026-02-30`) or does not match the order is a `FormatError`.

### 5.2 Month keys

A month key is `YYYY-MM`. Month keys sort correctly as strings. `iter_months(first, last)` includes both ends; `months_between(start, stop)` is half-open and excludes `stop`. A range written in a data file (rate files, section 6.1) always includes both of its end months.

### 5.3 Fiscal years

A fiscal year starts on the first day of the account's `fiscal_start` month (1 when absent) and is named after the calendar year in which it ends. With `fiscal_start` 4, April 2025 to March 2026 is FY2026. Quarters are numbered from the start of the fiscal year: with `fiscal_start` 4, January 2026 is in FY2026-Q4.

### 5.4 Weeks and business days

Weeks follow ISO 8601 (`ledger.periods.weeks`). A business day is a Monday to Friday that is not a public holiday of the statement's jurisdiction (`ledger.periods._holiday_table`); a statement without a jurisdiction only skips weekends. Business days are used by the aging report only.

## 6. Exchange rates

### 6.1 Rate files

A rate file is a CSV file with the columns `currency`, `from`, `to` and `rate`, in that order. Lines starting with `#` and blank lines are ignored. Each row says that, in every month from `from` to `to` (both included), one major unit of `currency` was worth `rate` US dollars. A row whose `from` and `to` are the same month covers exactly that month.

Rules:

- `rate` is a positive decimal written with digits and at most one `.`, with at most 8 decimal places. Exponent notation, signs and group separators are rejected.
- `from` and `to` are month keys and `to` is not before `from`.
- The base currency has no rows; a USD row is an error.
- Two rows that cover the same currency and month are a `RateConflict`, whether they are in one file or in two files loaded together.

The table built from a rate file (`RateTable`) holds exactly the months the rows cover, one entry per currency and month.

### 6.2 Which rate applies to a month

The rate for a currency in a month is chosen as follows:

1. If the rate table lists the month, that rate is used.
2. Otherwise the most recent earlier month that the table lists is used, provided it is at most three months before the month in question (`MAX_LOOKBACK`). The rate is then said to be carried from that month.
3. Otherwise there is no rate, and `MissingRate` is raised.

A later month's rate is never used, not even when it is closer than the nearest earlier one: it was not known at the time of the entry. Examples, with rates listed for January to March and for May:

| Month | Rate used |
|---|---|
| March | March |
| April | March (carried, one month back) |
| May | May |
| December of the year before | none: `MissingRate`, even though January is only one month later |

With rates listed only for January, April is carried from January (three months back) and May has no rate.

The base currency always has the rate 1 in every month.

### 6.3 Cross rates

The cross rate from currency A to currency B in a month is rate(A) / rate(B), each chosen as in 6.2, rounded to 6 decimal places with the rule of section 7.2. Converting an amount between two non-base currencies goes through the base currency exactly, and only the result is rounded to whole minor units of B.

## 7. Conversion and rounding

### 7.1 Converting one entry

An amount of `m` minor units of a currency with exponent `e`, at rate `r`, is worth exactly `m * r * 10^(2 - e)` US cents. This value is computed with exact decimal arithmetic (Python `Decimal`), never with binary floats.

Each entry is converted on its own and rounded to whole cents (7.2) before it is added to anything. Every total in every report (a month, a category, a tax code, a trial balance row, a report total) is a sum of rounded entry values. Totals are never rounded again, and an exact sum is never rounded as a whole. For example, two entries of 41.00 EUR at 1.0825 are each 4438.25 cents exactly; each rounds to 4438, and their month total is 8876, not the 8877 that rounding their exact sum 8876.5 would give.

### 7.2 The rounding rule

All rounding in the package rounds to the nearest integer, and a value exactly halfway between two integers is rounded away from zero:

| Exact value | Rounded |
|---|---|
| 216.5 | 217 |
| -216.5 | -217 |
| 2.5 | 3 |
| 3.5 | 4 |
| -0.5 | -1 |
| 10.49 | 10 |

The same rule applies when rounding to decimal places (cross rates, percentages, statistics): 1.23455 to four places is 1.2346. Rounding half to even ("banker's rounding") is not used anywhere, because it does not match the rounding the senders use on their own statements.

`ledger.core.rounding.round_half_away` implements this rule and every other module rounds through it (or through `round_to`, which uses the same rule).

### 7.3 Allocation

`allocate(total, weights)` splits an integer amount in proportion to weights with the largest remainder method; the shares always add up to the total. Remainders go one unit at a time to the largest fractional parts, earlier positions first on ties. Negative totals are allocated as their absolute value and negated.

## 8. Reversals

### 8.1 What a reversal is

An entry whose `reverses` column names another entry of the same statement cancels that entry. The entry it names is called the original.

### 8.2 Checks

A reversal must satisfy all of these, or `UnmatchedReversal` is raised:

- the original exists in the same statement;
- the original is itself a regular entry, not a reversal;
- the reversal's amount is exactly the negated amount of the original;
- the reversal is not dated before the original;
- no other reversal already cancels the same original.

### 8.3 Booking period and valuation

A reversal does not create an event of its own in the reports; it undoes the original. Therefore:

- it is booked in the period (month) of the original entry, not in the month in which it was posted;
- it is valued as of the original entry's date: it is converted at the rate that applies to the original's month (section 6.2), and when it is taxed, the tax rule in force on the original's date applies (section 10.2).

Both dates come from the original. In `ledger.book.reversals`, a `Booking` carries a `period_date` and a `valuation_date`; for a regular entry both are its own date, and for a reversal both are the original's date. A matched pair therefore nets to exactly zero in every report, in every currency and for tax, even when the reversal is posted in a later month whose exchange rate or tax rate differs.

Example: an entry of -150.40 EUR dated 20 January and its reversal dated 3 February both belong to January and are both converted at January's rate. The February report does not show either of them.

### 8.4 Reversals elsewhere

Splits (13.2) split a reversal with the same weights as its original, part by part. The audit (`ledger audit`) reports reversals posted more than 60 days after their original; this is informational only.

## 9. Categories and accounts

### 9.1 Resolution

The chart of accounts (`ledger.book._chart`) maps categories to account codes. A category is a dotted path such as `travel.rail.season`. An entry's category is resolved to the account of the longest listed prefix of its path: `travel.rail.night` uses the account of `travel.rail` when only that is listed, and `travel.bus` uses the account of `travel`. Categories are compared in lower case.

An empty category goes to the suspense account `9990`. A non-empty category with no listed prefix, or with an empty segment (`travel..rail`), is `UnknownCategory`.

### 9.2 Suggestions and rules

`ledger suggest` proposes categories for entries without one, from the merchant table. Suggestions are never applied by the reports. A rules file (`ledger.book.rules`) can assign categories to uncategorized entries before booking, when a caller applies it explicitly; reading a statement never applies rules.

## 10. Tax

### 10.1 Codes and jurisdictions

Tax codes are `S` (standard), `R` (reduced), `Z` (zero rated) and `E` (exempt). Each jurisdiction in `ledger.tax._rule_table` has, per code, a list of rules: a date from which a rate applies, and the rate. Rates in the table are written as fractions (`0.095`) or percentages (`9.5%`).

A statement is taxed in its layout's jurisdiction. An entry with a tax code in a statement without a jurisdiction, an unknown jurisdiction, an unknown code, or a date before the code's first rule is `UnknownTaxCode`. Entries without a tax code are not part of tax reports.

### 10.2 Which rule applies

The rule that applies on a day is the rule of the entry's code with the latest effective date that is on or before that day. A rule takes effect on its effective date itself: a rate that applies from 1 March 2026 applies to an entry valued on 1 March 2026, and the previous rate applies to an entry valued on 28 February 2026.

The day is the entry's valuation date (section 8.3): its own date for a regular entry, the original's date for a reversal.

### 10.3 Tax portion

Statement amounts include tax. For an entry, the gross amount G is its converted and rounded value in US cents (section 7.1). With rate r, the tax portion is G * r / (1 + r) rounded with the rule of 7.2, and the net amount is G minus the tax portion. Tax portions are computed per entry and then added up; they are never computed from a total.

Because the rounding rule is symmetric, the tax of a reversal is exactly the negated tax of its original.

### 10.4 Returns and schedules

A quarterly return (`ledger return`) adds the per-entry tax lines of one jurisdiction's statements by calendar quarter of their valuation dates. `ledger schedule` prints a jurisdiction's rules; each rule's "until" date is the effective date of the next rule of the same code, and the rule no longer applies on that date.

## 11. Reports

### 11.1 Monthly report

`build_monthly` returns:

    {"account": "...", "currency": "EUR", "base": "USD",
     "months": {"2026-01": -12345, ...}, "total": -12345}

`months` holds, for each booking period that has at least one entry, the sum of the rounded values of the entries booked in it (sections 7.1 and 8.3), in calendar order. A month whose entries cancel out is listed with 0. `total` is the sum of the month values.

### 11.2 Tax report

`build_vat` returns, per tax code used by the statement, the sums of the per-entry gross, net and tax amounts (section 10.3), plus `total_tax`, the sum of the tax amounts. Codes are listed in alphabetical order. A statement without taxed entries has an empty `codes` mapping.

### 11.3 Balances, summaries and comparisons

- Balances list every month from the first to the last month of a monthly report, months without entries included, with the movement and the closing balance.
- Fiscal summaries add month values by fiscal quarter and fiscal year (section 5.3).
- Month-over-month and year-over-year comparisons give percentages rounded to one decimal with the rule of 7.2, written with a sign (`+12.5%`). A change from zero is `new`.

### 11.4 Trial balance and account matrix

The trial balance and the account-by-month matrix are built from journal postings. A posting is one entry, booked and valued as in sections 7 and 8, assigned to the account of its category. An account's net is the sum of its postings; a positive net is shown as a debit and a negative net, as a positive number, as a credit.

### 11.5 Other reports

- Aging lists open receivables (positive regular entries in a `receivable` account that no reversal cancels) by business days outstanding, in buckets 0-20, 21-40, 41-60 and 61+. Amounts stay in the statement currency.
- Revaluation compares, at each month end, the book value (sum of posted rounded values) with the running balance converted once at that month's rate.
- Reconciliation compares sender-reported closing balances with the sum of entries by posting date. It deliberately ignores booking periods, because the sender does not know them.
- Budgets compare planned and actual account totals by month.

## 12. Rendering

All renderers take the report dicts of section 11 and show amounts in major units of US dollars with two decimals.

| Format | Decimal mark | Group separator | Negative amounts | Example |
|---|---|---|---|---|
| text | `.` | `,` | leading minus | `-1,234.56` |
| CSV | `.` | none | leading minus | `-1234.56` |
| Markdown | `.` | `,` | leading minus | `-1,234.56` |
| HTML | `.` | `,` | leading minus, cell class `neg` | `-1,234.56` |
| JSON | not applicable | not applicable | integer cents | `-123456` |

All of them use `ledger.core.money.format_amount`, whose output is defined in section 4.3; a renderer never formats amounts on its own. Small negative amounts keep their sign: -50 cents is `-0.50` in text, CSV, Markdown and HTML alike.

The accounting style (`format_accounting`) puts negative amounts in parentheses. It is only used where a caller asks for it explicitly; no report format uses it.

Text output: a title line, then a table whose columns are separated by two spaces, text left-aligned and amounts right-aligned, with trailing spaces removed from every line. The monthly report's last row is `total`.

CSV output: a header row, then one row per line of the report, lines ending with `\n`, fields quoted only when needed.

Markdown output: a `###` title, a blank line, and a pipe table whose amount columns are right-aligned (`---:`); the total row's label is bold.

JSON output: keys sorted, two-space indentation, a final newline.

## 13. Auxiliary files

### 13.1 Budgets

CSV with columns `account`, `month`, `amount`; amounts in US dollars with a `.` decimal mark, negative for spending. One line per account and month.

### 13.2 Splits

CSV with columns `id`, `category`, `weight`. An entry named in the file is replaced by one part per line, sharing its amount with `allocate` (section 7.3). Part ids get the suffix `/1`, `/2`, ... in file order.

### 13.3 Closing files

One month key per line; `#` starts a comment. `late_entries` lists the entries booked into a closed month although they were posted after that month ended (for instance a reversal posted in February of an entry from a closed January).

### 13.4 Balance files

CSV with columns `month` and `closing`; amounts in the statement currency with a `.` decimal mark.

### 13.5 Workspace file

`ledger.toml` may set `[ledger] rates`, `statements` and `pattern`, and `[report] format`. Unknown sections or keys are errors.

## 14. Command line

`python -m ledger <command>` runs from the workspace directory. Rates come from `--rates`, else from the `LEDGER_RATES` environment variable, else from `data/rates.csv` under the current directory. Output goes to standard output; errors go to standard error as `ledger: <ErrorType>: <message>` with exit status 2. `python -m ledger --help` and `python -m ledger <command> --help` list the commands and options.

### 14.1 Reports of one statement

| Command | Output |
|---|---|
| `report STATEMENT [--format F] [--detail]` | Monthly report (11.1). With `--detail`, one CSV line per entry: id, posting date, booking period, the month whose rate was used, and the value in US dollars. |
| `vat STATEMENT [--format F]` | Tax report (11.2). |
| `balances STATEMENT [--format F]` | Running balances (11.3). |
| `summary STATEMENT [--format F]` | Fiscal quarters and years (11.3). |
| `explain STATEMENT ID` | How one entry is read, booked, valued and taxed, one stage per line. |
| `revalue STATEMENT` | Month-end revaluation (11.5), as JSON. |
| `aging STATEMENT DATE` | Open receivables on DATE (11.5). |
| `audit STATEMENT` | Findings worth a second look; they never stop a report. |
| `suggest STATEMENT` | Category suggestions for uncategorized entries (9.2). |
| `outlook STATEMENT [--months N]` | Recurring payments projected forward, in the statement currency. |

`--format` is one of `text`, `csv`, `markdown` and `json` (section 12); `text` when absent.

### 14.2 Several statements

| Command | Output |
|---|---|
| `trial STATEMENT... [--period MONTH]` | Trial balance (11.4), optionally for one booking period. |
| `matrix STATEMENT...` | Account-by-month matrix (11.4), as JSON. |
| `transfers STATEMENT...` | Pairs of cash entries in different statements that cancel within a tolerance and lie at most three days apart. |
| `return STATEMENT...` | Quarterly tax return of one jurisdiction (10.4), as JSON. |
| `export STATEMENT...` | Postings as plain-text double-entry transactions. |
| `budget BUDGET STATEMENT...` | Budget against actual (13.1), as CSV. |
| `overview STATEMENT...` | One line per statement: currency, dialect, entries, reversals, date range. |

### 14.3 Files and tables

| Command | Output |
|---|---|
| `check STATEMENT... [--guess]` | One line per statement: `ok` with the layout it was read with, or `FAIL` with the first problem. Exit status 1 when any statement fails. With `--guess`, also compares each file's body with that layout (3.6). |
| `validate STATEMENT` | Every row-level problem of a statement, not only the first. |
| `diff OLD NEW` | Entries added, removed or changed between two versions of a statement, and layout changes. |
| `rate CURRENCY MONTH` | The rate that applies (6.2) and the month it comes from. |
| `rates` | Per currency: listed range, missing months, low, high, mean and spread of the rates. |
| `dialects [NAME]` | The dialect table, or one dialect's layout. |
| `schedule JURISDICTION` | Every tax rule of a jurisdiction with the date it ends (10.4). |

## 15. Errors

Every error the package raises on purpose is a `LedgerError`. `FormatError` (and its subclass `HeaderError`) carry the file and one-based line when they come from a file, and show them as `path line N: message`. Errors are raised, never logged and skipped: a statement either reads completely or not at all.

## 16. Worked examples

The examples use these rates: EUR 1.0825 for January to March 2026 (one row), EUR 1.0910 for May and June 2026, and nothing for April.

### 16.1 One entry from file to report

A row `b3,2026-02-02,Rail pass,-84,,travel.rail.season,R` in a EUR statement with jurisdiction ARD:

1. Amount: `-84` has no fraction, so it is -8400 minor units (4.2).
2. Booking: a regular entry, so period and valuation date are its own date, 2 February 2026 (8.3).
3. Rate: February is listed, rate 1.0825 (6.2).
4. Conversion: -8400 * 1.0825 = -9093.0000 cents exactly, -9093 after rounding (7.1).
5. Account: `travel.rail.season` is listed, account 5211 (9.1).
6. Tax: code R in ARD on 2 February 2026; the reduced rule in force on that day is 9.5% from 15 October 2025 (10.2). Tax portion -9093 * 0.095 / 1.095 = -788.89..., rounded -789; net -8304 (10.3).

### 16.2 A month without a listed rate

An entry of 100.00 EUR dated 10 April 2026 uses March's rate, 1.0825, carried one month (6.2): 10825 cents. It does not use May's rate, although May is listed and equally close. An entry dated 10 December 2025 has no rate at all, because no earlier month is listed: `MissingRate`.

### 16.3 A reversal posted in a later month

Entry x2 of -150.40 EUR on 20 January 2026 is reversed by x3, +150.40 EUR on 3 February 2026. Both are booked in January and both are converted at January's rate: -16281 and +16281 cents. January's total includes both; February's does not include x3. If January and February had different rates, x3 would still use January's. If the tax rate changed on 1 February, x3 would still be taxed at the rate in force on 20 January.

### 16.4 Rounding a month

A EUR statement with two entries of 41.00 in February at 1.0825: each is 4438.25 cents exactly and 4438 rounded. February's total is 8876. Rounding the exact sum, 8876.5, would give 8877 under 7.2 and 8876 under half-to-even rounding; neither is how totals are formed, because totals add rounded entries.

### 16.5 Precedence of header lines

A statement with `#dialect: lowmarsh` and `#date_order: dmy` is read with `dmy` dates whatever date order the `lowmarsh` dialect records, and with the dialect's delimiter, decimal mark and jurisdiction for the keys the header leaves out (3.4). `python -m ledger check FILE` prints the layout actually used.

### 16.6 Negative amounts in output

A month total of -50 cents is shown as `-0.50` in text, CSV, Markdown and HTML, and as `-50` in JSON. A total of -123456 cents is `-1,234.56` in text, Markdown and HTML and `-1234.56` in CSV (section 12).
