# west

Semicolon-separated text with a header row.

- Directives in `#` comment lines: `# seq: N` and
  `# weight unit: <unit> (decimal comma)`. West has exported in pounds for a
  long time, but the unit line of each file is what counts.
- Some exports come from an older office system and declare
  `# charset: windows-1252`.
- Columns: `id` (for example `SH123456`), `typ` (`N`, `C` or `V`), `shipped` as
  `DD.MM.YYYY`, `weight`, `status`, `note`.
- Weights use a comma as the decimal separator and a dot to group thousands:
  `12,5`, `1.234,50`. Whole values are often written without a decimal part,
  so `1.250` is one thousand two hundred fifty, and `183` is 183.
- Status values are upper case with spaces: `DELIVERED`, `DELIVERED LATE`,
  `CANCELLED`, `RETURNED`, `HELD`.
