# river

Tab-separated text with a header row.

- Directives in `#` comment lines: `# seq: N`, `# date format: MM/DD/YYYY` or
  `# date format: DD/MM/YYYY`, and `# weight unit: g|kg`. The date format can be
  changed part way through a file by another date format directive; it applies
  to the rows after it.
- Columns: `t` (empty for a new record, `C` correction, `V` void), `ref` (for
  example `SH/123456`), `shipped`, `weight`, `status`.
- Status values: `delivered`, `delivered-late`, `cancelled`, `returned`, `held`.
- The last line is a `# N records` comment.
- River's newer export stations write UTF-16 with a byte order mark; older ones
  write UTF-8.
