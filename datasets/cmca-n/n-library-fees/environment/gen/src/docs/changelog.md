# Changelog of the fee rules

## 4.0 (2026-09)

- A loan past its grace allowance is charged for every overdue day, the
  first ones included (`fees.md` 1.2). Up to 3.x the grace days were
  deducted from the charged days.
- Exemptions and discounts follow the patron's category on the checkout
  date (`fees.md` 2.2 and 2.4); the statement cap follows the category on
  `period_end` (`fees.md` 4.1). 3.x used the category on `period_end` for
  all three.
- `*` waivers cover every loan of a patron's statement (`lending.md` 6).

## 3.1 (2026-03)

- The discount is rounded half up to a whole cent (`fees.md` 2.4). 3.0
  rounded half to even, so 62.5 cents became 62.
- The loan cap is applied before the discount (`fees.md` 2.3 and 2.4).

## 3.0 (2025-11)

- Only days on which the checkout branch is open are overdue days
  (`fees.md` 1.1). Up to 2.x every calendar day after the due date counted.
- A book-drop return is dated the day before it is checked in (`loans.md`
  4.2).
- `calendar.csv` takes ranges of days and `open` rows; a row for one branch
  takes precedence over a `*` row for the same day (`lending.md` 3.5).

## 2.0 (2025-04)

- JSON Lines exports write instants in UTC or with an offset; local dates
  come from the `[clock]` section of `policy.ini`, which lists the changes of
  the library's offset (`exports.md` 5).
- The excess over the statement cap is taken from the loans due last
  (`fees.md` 4.2), so the oldest charges stay on the bill.
- Renewals made after the due date, or beyond the renewal limit, do not
  count (`loans.md` 3.1).
