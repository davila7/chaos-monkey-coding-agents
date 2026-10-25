# Stock: ledger, lots, reorder

## 1. Movements

1.1 The ledger records movements in the order they happen. Each movement has
a sequence number (from 1), a kind, a sku, a signed quantity, a date and a
site (default `main`).

| Kind | Effect |
|---|---|
| `receipt` | adds a new lot with the received quantity |
| `issue` | takes units from the oldest lots first |
| `adjust` | changes the quantity of one named lot; a lot that reaches 0 is gone |
| `transfer` | moves units to another site, oldest lots first |

1.2 A movement dated before the last recorded movement raises `LedgerError`.
So does an issue or transfer of more units than the site holds, an
adjustment that would take a lot below 0, a receipt of a lot id the site
already holds for that sku, and a quantity of 0 or less where a positive one
is needed. A refused movement changes nothing.

1.3 A movement without a date is dated with the business date
(`overview.md` 3).

## 2. Lots

2.1 A lot keeps the date it was received. Lots are used oldest first (by
received date, then lot id). A transfer moves units lot by lot; the lots keep
their ids and received dates at the new site, and units of a lot id the new
site already holds are added to it.

2.2 `lots(sku, site)` lists the lots in stock, oldest first.
`on_hand(sku, site)` is the sum of their quantities.

## 3. Issued quantities

`issued(sku, since, until, site)` is the number of units issued from `since`
to `until`, both dates included. Transfers are not issues.

## 4. Aging

4.1 `aging(as_of, site)` lists every lot in stock as `(sku, lot, qty, age)`,
where age is the number of days from the received date to `as_of`. Without
`as_of` the business date is used.

4.2 Rows are sorted oldest first (highest age), then by sku, then by lot id.

## 5. Reorder points and suggestions

5.1 Daily demand is the number of units issued over the `reorder.demand_days`
days that end on the reference date (both ends included), divided by that
number of days, rounded half to even to 4 places.

5.2 The reorder point is daily demand times (lead days of the item plus
`reorder.safety_days`), rounded up to a whole unit.

5.3 `suggestions(ledger, catalog, settings, as_of, site)` gives one suggestion
per item, by sku, whose reorder point is above 0 and whose stock on hand is at
most the reorder point. A suggestion orders enough whole cases to reach the
reorder point plus the demand until the next review (daily demand times the
days from `as_of` to the next review, rounded up), and at least one case.

## 6. Review dates

6.1 Stock is reviewed once a month. `next_review(last, settings)` gives the
review after one held on `last` (the business date when left out).

6.2 The next review is in the month after `last`, on the same day of the
month as `last`, or on `reorder.review_day` when that is set. When the month
has no such day, the review is on its last day: after 2027-01-31 comes
2027-02-28, after 2028-01-30 comes 2028-02-29. After a review in December
comes one in January of the next year.

6.3 A `review_day` outside 1 to 31 raises `SettingsError`.
