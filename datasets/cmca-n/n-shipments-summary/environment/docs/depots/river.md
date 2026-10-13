# river

Family: delimited text, tab-separated.

- Directives: `# seq: N`, `# date format: <form>` and `# weight unit: <unit>`.
  Base date form: `MM/DD/YYYY`.
- Columns: `t` (empty for a new record, `C` correction, `V` void), `ref` (for
  example `SH/123456`), `shipped`, `weight`, `status`.
- Weights use a dot as the decimal separator.
- Status values: `delivered`, `delivered-late`, `cancelled`, `returned`, `held`.
- The last line is a `# N records` comment.
