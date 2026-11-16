# Loans

## 1. Checkouts

1.1 A loan starts with a checkout event that is not cancelled. The loan id
is the `loan` of the checkout, the patron is its `patron`, the item type its
`item_type`, the checkout branch its `branch`, and the checkout date its local
date. Two checkouts that count never share a loan id.

1.2 A checkout dated after `period_end` is not part of the run, and neither
are the events of its loan.

1.3 A renewal or a return whose loan id has no checkout that counts belongs
to no loan and changes nothing.

## 2. The due date

2.1 The due date of a loan is its checkout date plus `loan_days` of the item
type.

2.2 When the checkout branch is closed on that day (`lending.md` 3.5), the
due date moves to the next day on which the checkout branch is open.

## 3. Renewals and returns

The renewals and returns of a loan are taken in the order of their local
times. Two events of one loan never share a local time.

3.1 A renewal counts only when all of these hold:

- (a) its local date is on or before the due date of the loan at that moment;
- (b) the loan has fewer counted renewals than `renewals` of the item type;
- (c) its local date is on or before `period_end`.

A renewal that does not count changes nothing; in particular it does not use
up one of the renewals of (b).

3.2 A counted renewal sets the due date to its local date plus `loan_days`,
moved to the next open day of the checkout branch as in 2.2.

3.3 The first return ends the loan. Events of the loan after it change
nothing.

## 4. The return date

4.1 The return date of a loan is the local date of its return event.

4.2 A return with `via` `dropbox` came through the book drop, which is
emptied and checked in at the start of a working day. Its return date is the
day before the local date of the return event.

## 5. The period

5.1 The fee run is made as of `period_end`. A loan whose return date is
after `period_end` is still out at the end of the period, and its return is
not used by this run. A book-drop return checked in after `period_end` can
still have a return date inside the period (4.2).

5.2 The loans of the run are the loans of section 1 that were not returned
before `period_start`: a loan with a return date before `period_start` is
not part of the run.
