# east

Comma-separated values with a header row, quoted as usual for CSV: a field that
contains a comma, a quote or a line break is wrapped in double quotes.

- The file starts with `#` comment lines. Directives among them: `# seq: N`,
  `# unit: kg|lb` (the unit of `gross` and `net`) and `# dates: YMD|DMY`. YMD
  dates look like `2026-03-04`; DMY dates like `04-03-2026`.
- Columns: `id`, `type` (`N`, `C` or `V`), `shipped`, `gross`, `net`, `status`,
  `note`. The shipment weight is `gross`; `net` is the weight without packing
  and is not used.
- Large weights carry a comma as thousands separator (`"1,234.50"`); the decimal
  separator is always a dot.
- An export that was assembled from several batches has a `# batch N` comment
  where a batch starts, possibly new directives, and a new header row. The
  columns of a later batch can be in a different order. Directives and header
  rows apply from where they appear.
- Notes can span lines inside quotes, and a continuation line inside a quoted
  note can start with any character, including `#`. A `#` starts a comment only
  at the start of a line outside a quoted field.
- The last row has `TOTAL` in the id column. It is not a shipment.
- Status values vary in case and use either `_` or a space: `Delivered`,
  `delivered late`, `Delivered_late`, `Cancelled`, and so on.
