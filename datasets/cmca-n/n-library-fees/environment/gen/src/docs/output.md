# The statements file

## 1. Layout

1.1 The statements file is one JSON object, written as UTF-8:

    {
      "library": "Riverside Public Library",
      "period": {"start": "2027-02-01", "end": "2027-02-28"},
      "statements": [
        {
          "patron": "P-981",
          "category": "senior",
          "loans": [
            {"loan": "L0012345", "item": "31234567890", "item_type": "book", "branch": "CEN",
             "checkout": "2027-01-11", "due": "2027-02-01", "returned": "2027-02-08",
             "overdue_days": 5, "charged_days": 5, "assessed": 63, "waived": 0, "capped": 0, "billed": 63}
          ],
          "assessed": 63, "waived": 0, "capped": 0, "billed": 63
        }
      ],
      "branches": [
        {"branch": "CEN", "loans": 1, "charged_days": 5, "assessed": 63, "waived": 0, "capped": 0, "billed": 63}
      ]
    }

1.2 `library` is copied from `policy.ini`. `period` holds `period_start` and
`period_end`.

## 2. One statement

2.1 `statements` has one entry per patron with a statement (`fees.md` 5),
sorted by patron number as a number.

2.2 `patron` is the patron number as `patrons.csv` writes it. `category` is
the patron's category on `period_end`, as `policy.ini` names it.

2.3 `loans` lists the loans of the statement sorted by due date, then by loan
id as text.

2.4 `assessed`, `waived`, `capped` and `billed` are the sums of the same
fields over the loans of the statement.

## 3. One loan

3.1 `loan` is the loan id and `item` the item barcode, as the checkout writes
them. `item_type` is the item type as `policy.ini` names it. `branch` is the
checkout branch.

3.2 `checkout` and `due` are the checkout date and the due date
(`loans.md` 2 and 3), written `YYYY-MM-DD`.

3.3 `returned` is the return date when it is on or before `period_end`, and
`null` for a loan still out at the end of the period.

3.4 `overdue_days` and `charged_days` follow `fees.md` 1. `assessed` is the
assessed fee (`fees.md` 2), `waived` the waived amount (`fees.md` 3), `capped`
what the loan gave up to the statement cap (`fees.md` 4) and `billed` the
billed fee. All amounts are whole cents.

## 4. The branch summary

4.1 `branches` has one entry per branch of `branches.csv`, in the order of
that file, branches without loans on any statement included.

4.2 `loans` counts the statement loans whose checkout branch is the branch.
`charged_days`, `assessed`, `waived`, `capped` and `billed` are the sums of
the same fields over those loans.

## 5. Checking

From `/app`:

- `python -m unittest discover -s tests -t .` runs the program on a few small
  inputs and compares each result with the reviewed one next to it.
- `python tools/check_fees.py` runs the program on `/app/data` and on a copy
  of it in another directory, compares `/app/out/statements.json` with the
  approved statements of the current period and names the first statements
  that differ. The approved statements are stored as salted digests, so the
  check says whether a statement is right, never what it should hold.
