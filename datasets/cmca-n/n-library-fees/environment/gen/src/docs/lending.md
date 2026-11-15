# The lending files

## 1. policy.ini

1.1 `policy.ini` is an INI file: sections in square brackets, one
`key = value` per line, and comment lines that start with `#`. Values have no
quotes. Amounts of money are written in currency units with two decimals
(`0.25`) and stand for whole cents (25).

1.2 Section `[statement]`: `library` (the library's name), `period_start` and
`period_end` (dates `YYYY-MM-DD`, both included in the period).

1.3 Section `[clock]`: the library's offset from UTC.

- `offset` is the offset in force before the first change, written `-06:00`.
- `changes` lists the changes, separated by `;`, in time order. Each change
  is an instant in UTC written `YYYY-MM-DDTHH:MMZ`, a space and the offset in
  force from that instant on. `changes` can be empty.

1.4 One section `[item:TYPE]` per item type (`[item:book]`, `[item:dvd]`):

- `loan_days`: days from a checkout or a counted renewal to the due date
  (`loans.md` 2 and 3);
- `renewals`: the most renewals of one loan that count (`loans.md` 3.1);
- `grace_days`: the grace allowance (`fees.md` 1.2);
- `daily`: the fee per charged day;
- `loan_cap`: the most that one loan of this type is assessed before a
  discount (`fees.md` 2.3).

1.5 One section `[category:NAME]` per patron category:

- `statement_cap`: the most that one statement of a patron of this category
  bills (`fees.md` 4), or `none` for no cap;
- `discount`: a whole percentage taken off the fee of each loan (`fees.md`
  2.4), 0 for none;
- `exempt`: item types, separated by commas, whose loans this category is
  never charged for (`fees.md` 2.2); it can be empty.

Item types and category names are compared without regard to case.

## 2. branches.csv

2.1 Columns `branch`, `name`, `open_days`. `open_days` lists the weekdays on
which the branch opens, as three-letter English names separated by spaces
(`Tue Wed Thu Fri Sat`).

2.2 The order of the rows is the order of the branch summary (`output.md`
4.1).

## 3. calendar.csv

3.1 Columns `date`, `branch`, `status`, `note`. The note carries nothing for
the fee run.

3.2 `date` is one day (`2027-02-15`) or a range of days `FIRST..LAST`
(`2027-01-28..2027-02-04`), both days included.

3.3 `branch` is a branch id, or `*` for every branch.

3.4 `status` is `closed` or `open`. An `open` row opens the branch on a day it
would otherwise be closed: a holiday, or a weekday that is not in its
`open_days`.

3.5 Whether a branch is open on a day:

- if a row naming that branch covers the day, its status decides;
- otherwise, if a `*` row covers the day, its status decides;
- otherwise the branch is open when the weekday is in its `open_days`.

Two rows of the same kind (one branch, or `*`) never cover the same day.

## 4. patrons.csv

4.1 Columns `patron`, `category`, `since`, `home_branch`. A patron has one
row per category they have held; `since` is the first day of that category.

4.2 The category of a patron on a day is the category of their row with the
latest `since` on or before that day.

## 5. Patron numbers

5.1 Exports and waivers write the patron number in several ways: with or
without the letter `P` in either case, with or without a hyphen or a space
after it, with or without leading zeros. `P-981`, `p981`, `P000981`,
`0000981`, `p-000981` and `P 981` are the same patron. Two patron numbers are
the same patron when their digits give the same number.

5.2 Statements name the patron as `patrons.csv` writes the number.

## 6. waivers.csv

6.1 Columns `waiver`, `patron`, `loan`, `value`, `status`.

- `loan` is a loan id, or `*` for every loan of the patron's statement.
- `value` is `full`, or an amount.
- `status` is `active` or `revoked`. A revoked waiver does nothing.

6.2 How waivers reduce a fee is in `fees.md` 3.
