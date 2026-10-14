# lakeside

Family: delimited text, comma-separated with CSV quoting.

- Directives: `# seq: N` and `# dates: <form>`. Base date form: `iso`.
- Columns: `id` (for example `sh123456`), `kind` (empty for a new record, `corr`
  or `void`), `booked` (booking date), `shipped` (ship date), `gross_kg`,
  `net_kg`, `status`. The shipment weight is `gross_kg`; `net_kg` is not used.
  Both dates follow the date directive in force.
- Weights use a dot as the decimal separator.
- Status values are lower case with hyphens: `delivered`, `delivered-late`,
  `cancelled`, `returned`, `held`.
