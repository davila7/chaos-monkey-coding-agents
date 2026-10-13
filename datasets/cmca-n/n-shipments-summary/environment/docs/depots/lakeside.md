# lakeside

Comma-separated values with a header row.

- Directives in `#` comment lines: `# seq: N` and `# dates: iso|serial`. ISO
  dates look like `2026-03-04`. Serial dates are day numbers counted the way
  spreadsheets do: day 1 is 1899-12-31, so 46085 is 2026-03-04. A dates
  directive applies to the rows after it.
- Columns: `id` (for example `sh123456`), `kind` (empty for a new record, `corr`
  or `void`), `booked` (booking date), `shipped` (ship date), `gross_kg`,
  `net_kg`, `status`. The shipment weight is `gross_kg`, in kilograms.
- When the export tool's column set changes during a run, it writes a
  `# columns changed` comment followed by a new header row; the rows after it
  follow the new header.
- Status values are lower case with hyphens: `delivered`, `delivered-late`,
  `cancelled`, `returned`, `held`.
