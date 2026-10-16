# Commands

All commands take the global `--store DIR` before the command name. Output
goes to standard output unless a command has `--out`.

## 1. collections, schema, head

- `collections [--names-only]`: each collection with its live record count
  and number of part files.
- `schema COLLECTION [--json]`: the fields of a collection.
- `head COLLECTION [-n N]`: the first N live records in store order as JSON
  lines (10 when `-n` is left out).

## 2. count

`count COLLECTION [--where FIELD=VALUE]...`

Prints the number of live records for which every `--where` holds. A
`--where` holds when the field's value, written as the query table writes it
(section 3), equals VALUE exactly. Null values never match.

This is a plain equality test. It shares nothing with the expression language
of `export` (`export.md`, section 5).

## 3. query

`query COLLECTION [--fields F1,F2,...] [--where FIELD=VALUE]... [--sort=[-]FIELD] [--limit N]`

Prints a text table. Values are written without a locale: dates and
datetimes in ISO form, booleans as `true`/`false`, nulls as empty cells, line
breaks inside strings as spaces. Numeric columns are right-aligned.

`--sort FIELD` sorts ascending by one field and `--sort=-FIELD` descending
(write it with `=`, since the value starts with `-`).
Records with a null value come last in both directions. `--limit` shows at
most N records (50 when left out, 0 for all).

The table is for people; its layout may change.

## 4. stats

`stats COLLECTION [--fields F1,F2,...]`

Per field: the number of values, nulls and distinct values, the smallest and
largest value, and the sum for numeric fields.

## 5. report

`report COLLECTION --by FIELD --sum FIELD [--locale NAME] [--format text|csv] [--out PATH]`

Groups the live records by one field and totals a numeric field, with a total
row. Groups are listed in ascending order of their value, the null group
(`(none)`) last.

With `--locale`, totals are written with the locale's decimal separator and
its group separator between groups of three digits, and day values with the
locale's `date` pattern (only `YYYY`, `MM` and `DD` are supported in report
headings). Report does not apply `group_sizes`, `min_grouping` or `minus`
from the locale table yet; negative totals are written with `-`.

`--format csv` writes the same rows as CSV for spreadsheets: LF line ends,
fields quoted only where Python's `csv` module requires it. This is not the
export format.

## 6. validate

`validate [COLLECTION...] [--max-problems N]`

Checks records against their schemas (`store.md`, section 5). Exits with
status 3 when it finds a problem.
