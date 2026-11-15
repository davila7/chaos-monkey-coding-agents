# Fees

All amounts are whole cents. `policy.ini` values are those of the item type
of the loan and of the patron's category named in each rule.

## 1. Overdue days

1.1 The overdue days of a loan are the days after its due date, up to and
including its end day, on which the checkout branch is open (`lending.md`
3.5). The end day is the return date, or `period_end` for a loan still out at
the end of the period (`loans.md` 5.1). Days on which the checkout branch is
closed are never overdue days, whatever branch the item is returned to.

1.2 Grace allowance, by `grace_days` of the item type:

- A loan with no more overdue days than `grace_days` is charged for none of them.
- A loan with more overdue days than `grace_days` is charged for every one of its overdue days, the first ones included.

1.3 The charged days of a loan are the overdue days it is charged for.

## 2. The assessed fee of a loan

2.1 The base fee is the charged days times `daily`.

2.2 When the item type is listed in `exempt` of the patron's category on the
checkout date, the base fee is 0.

2.3 The base fee is cut to `loan_cap` when it is higher.

2.4 The discount of the patron's category on the checkout date is taken off
the result of 2.3: the assessed fee is that amount times (100 minus
`discount`) divided by 100, rounded to a whole cent, with half a cent
rounded up. With a discount of 50, 125 cents give 63.

## 3. Waivers

3.1 A waiver applies to a loan of a statement when it is active, its patron
is the patron of the loan (`lending.md` 5), and its `loan` is the loan id or
`*`.

3.2 When a waiver that applies is `full`, the waived amount is the assessed
fee. Otherwise the waived amount is the sum of the amounts of the waivers that
apply, but never more than the assessed fee. A `*` waiver with an amount
applies that amount to each loan of the statement.

3.3 The net fee of a loan is its assessed fee minus its waived amount.

## 4. The statement cap

4.1 The statement cap is `statement_cap` of the patron's category on
`period_end`. With `none` there is no cap.

4.2 When the net fees of the loans of a statement add up to more than the
cap, the excess is capped. It is taken from the loans in order of due date,
latest first, and for loans with the same due date, from the loan id that
sorts last as text first. Each loan gives up as much of its net fee as the
excess still needs, and no more than its net fee.

4.3 The billed fee of a loan is its net fee minus what it gave up to the cap.

## 5. Which loans are on a statement

5.1 A statement lists every loan of the patron that is part of the run
(`loans.md` 5.2) and has at least one overdue day, including loans charged
nothing because of grace, an exemption or a waiver.

5.2 A patron with no such loan gets no statement.
