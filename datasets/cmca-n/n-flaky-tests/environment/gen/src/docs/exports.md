# Exports and the standard CSV files

## 1. Format

1.1 Exports are CSV files in UTF-8 with `\n` line ends. The first row names
the columns. Cells are quoted only where CSV needs it.

1.2 A cell of `None` is empty; `True` and `False` are written `yes` and `no`;
anything else is written with `str`.

## 2. Writing a file

2.1 `ReportWriter(target, columns)` writes one file. Column names must be
distinct and there must be at least one; otherwise it raises `ReportError`.
It is used as a context manager; `row(values)` adds a row, and a row with a
different number of cells than there are columns raises `ReportError`.
`write_report(target, columns, rows)` does the same for a list of rows and
returns the number of rows written.

2.2 The directory of the target must exist; otherwise entering the writer
raises `ReportError`.

2.3 While the writer is open, its rows go to a spool file. The target is
created or replaced only when the `with` block ends without an exception, in
one step, so a reader never sees half a file and the target keeps its old
content until then.

2.4 When the block ends with an exception, the exception propagates, the
target is left as it was, and the export leaves no file behind: no spool
file remains, in the target directory or anywhere else.

2.5 Exports are independent: several writers may be open at the same time,
also for targets with the same file name in different directories, and no
export ever sees rows of another one, whether that other export is still
open, finished, or failed earlier in the same process.

## 3. Standard files

All standard files go through `write_report`, and each function returns the
number of rows.

3.1 `stock_report(ledger, catalog, settings, target, site)`: one row per item
with stock at the site (the `site` setting when left out), by sku: `sku`,
`name`, `on_hand`, `unit_weight` and `total_weight` (both with
`format_weight`, `settings.md` 3.3), `tags` (sorted, separated by spaces).

3.2 `aging_report(ledger, target, as_of, site, older_than)`: the rows of
`aging` (`stock.md` 4) whose age is at least `older_than` days: `sku`, `lot`,
`qty`, `age_days`.

3.3 `reorder_report(ledger, catalog, settings, target, as_of)`: the
suggestions for the `site` setting (`stock.md` 5): `sku`, `on_hand`,
`reorder_point`, `order_qty`, `review`.

3.4 `freight_sheet(catalog, spec, zone, target)`: one row per item, by sku:
`sku`, `billable_kg` (with the item dimensions), `price` (`format_cents` of
the quote for one unit).
