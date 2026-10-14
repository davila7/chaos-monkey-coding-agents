# east

Family: delimited text, comma-separated with CSV quoting.

- Directives: `# seq: N`, `# unit: <unit>` (the unit of `gross` and `net`) and
  `# dates: <form>`. Base date form: `YMD`.
- Columns: `id` (for example `SH-12345`), `type` (`N`, `C` or `V`), `shipped`,
  `gross`, `net`, `status`, `note`. The shipment weight is `gross`; `net` is the
  weight without packing and is not used.
- Weights use a dot as the decimal separator and a comma to group thousands
  (`"1,234.50"`).
- `note` is free text and can span lines.
- The last row has `TOTAL` in the id column and is not a shipment.
- Status values vary in case and use either `_` or a space: `Delivered`,
  `delivered late`, `Delivered_late`, `Cancelled`, and so on.
