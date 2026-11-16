# Overdue fee statements: overview

The library lends books, DVDs, magazines, laptops and kits from its
branches. Once a month the fee run reads the circulation exports of every
branch together with the lending policy, and writes one fee statement per
patron with overdue loans and a summary per branch. This note says what goes
in, what comes out and in which order the work is done. The rules for each
step live in their own notes:

| Note | Covers |
|---|---|
| `lending.md` | the lending files: policy, branches, calendar, patrons, waivers |
| `exports.md` | the circulation export files and their events, local times, voids |
| `loans.md` | how events become loans: due dates, renewals, returns, the period |
| `fees.md` | overdue days, grace, the fee of a loan, waivers, the statement cap |
| `output.md` | the statements file |
| `changelog.md` | what changed between versions of these rules |

Where this note and a numbered rule in another note seem to disagree, the
numbered rule wins. The rules apply to every run the same way: nothing in
them depends on a particular branch, patron, item or month.

## 1. Inputs

1.1 An input directory holds `policy.ini`, `branches.csv`, `calendar.csv`,
`patrons.csv` and `waivers.csv` (`lending.md`), and a directory `exports/`
with the export files of the branches (`exports.md`).

1.2 The exports are raw: they overlap, they repeat events, they hold events
that were cancelled later, and they run a few days past the end of the
statement period. `exports.md` and `loans.md` say which events count.

## 2. Steps

1. Read the lending files (`lending.md`).
2. Read every export file and keep the events that count (`exports.md`).
3. Build the loans of the run from their events: due dates, renewals and
   returns (`loans.md`).
4. For each loan, count its overdue days and work out its fee, its waivers
   and, per patron, the statement cap (`fees.md`).

Then write the statements and the branch summary to one file (`output.md`).

## 3. Terms

- A **loan** is one checkout of one item by one patron, with the renewals and
  the return that follow it (`loans.md`).
- The **period** runs from `period_start` to `period_end` of `policy.ini`,
  both days included.
- The **checkout branch** of a loan is the branch where it was checked out.
  Due dates and overdue days follow the calendar of the checkout branch,
  wherever the item is returned.
- An amount of money is a whole number of cents.

## 4. Running the program

4.1 The program reads one input directory and writes one statements file:

    python3 /app/bin/fees.py INPUT_DIR OUTPUT_FILE

It uses only the Python standard library, reads nothing outside `INPUT_DIR`
and writes nothing but `OUTPUT_FILE`. The same input gives the same output
wherever the input directory is, and whatever the order in which the files of
`exports/` are listed.

4.2 The input is valid: every file named in these notes parses, every item
type of an export has a section in `policy.ini`, every patron of an export
has a row in `patrons.csv` dated on or before each of their checkouts, and
the other guarantees the notes state hold. A program does not have to check
this.

## 5. What the statements are used for

The statements are mailed as they are and the branch summary goes to the
finance office. One day counted wrong, one cent rounded the wrong way or one
waiver missed makes a statement wrong.
