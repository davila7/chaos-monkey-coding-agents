# Circulation exports

## 1. Files

1.1 `exports/` holds the files that the circulation system of each branch
exports. Only files whose names end in `.csv` or `.jsonl` are exports. Other
files are not: the manifest, and files that a branch is still writing, which
end in `.part` until they are complete.

1.2 A file is UTF-8 text with LF line ends. It can begin with a byte order
mark.

1.3 Exports overlap. A branch exports a span of days, and its next file can
start up to two days before the previous one ended; a resend file repeats
events that a branch sent again. An event is identified by its `event` id: it
appears in any number of files, always with the same fields, and it counts
once.

## 2. CSV exports

2.1 The first line names the columns. The order of the columns differs
between files, and some files carry more columns than section 4 names; a
program finds the columns by name and ignores the others. A cell with nothing
to say is empty.

2.2 Column `time` is the local time of the event at the library, written
`YYYY-MM-DD HH:MM` (section 5).

## 3. JSON Lines exports

3.1 Each line is one JSON object with the fields of section 4, except that
`at` takes the place of `time`. Fields with nothing to say are left out.

3.2 `at` is the instant of the event, written in ISO 8601 with seconds and
either `Z` (UTC) or an offset from UTC: `2027-02-03T04:12:00Z`,
`2027-02-02T22:12:00-06:00`. Both forms name an instant; section 5 turns it
into a local time.

## 4. Fields of an event

| Field | Holds |
|---|---|
| `event` | the event id |
| `type` | `checkout`, `renew`, `return` or `void`, in any case |
| `loan` | the loan id (checkout, renew, return) |
| `patron` | the patron number (checkout), in any of the forms of `lending.md` 5 |
| `item` | the item barcode (checkout, return) |
| `item_type` | the item type (checkout), in any case |
| `branch` | the id of the branch where the event happened |
| `via` | `desk`, `self`, `online` or `dropbox` |
| `target` | the event id that a void cancels (void only) |

## 5. Local time

5.1 Every rule of these notes works on local dates of the library. The local
time of a CSV event is its `time`. The local time of a JSON Lines event is
its instant shifted by the offset of `policy.ini` `[clock]` in force at that
instant (`lending.md` 1.3).

5.2 The local date of an event is the date of its local time.

## 6. Voids

6.1 A `void` event cancels the event named by its `target`. A cancelled event
counts nowhere: a cancelled checkout starts no loan, a cancelled renewal or
return does not happen.

6.2 A void is not an event of any loan, and voids are never cancelled.
