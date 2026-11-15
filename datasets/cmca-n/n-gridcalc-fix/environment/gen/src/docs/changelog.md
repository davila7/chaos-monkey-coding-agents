# Changelog

## 2.2.0

- `cell` prints the value of one cell (`overview.md` 4.3).
- Ranges may be written from any corner (`formulas.md` 4.2).
- Text that holds a number is skipped inside the references given to `SUM`,
  `AVERAGE`, `MIN`, `MAX` and `COUNT`, as other text is (`functions.md` 2.1,
  3.1). Up to 2.1 it was counted as a number, which made `'42` and `42`
  behave the same in a range.

## 2.0.0

- Operator precedence follows `formulas.md` section 3. The prefix minus is
  looser than `^` and `^` groups to the right, so `-2^2` is -4 and `2^3^2` is
  512. Up to 1.x the prefix minus bound tighter than `^` and `^` grouped to the
  left, as in some spreadsheet programs; that operator order is withdrawn
  (see `archive/2024-operator-order.md`).
- A cell the sheet does not define reads as empty, not as 0
  (`values.md` 1.4, 2.5). `A9&"x"` is `x` and `COUNT(A9)` is 0.
- `IF` and `IFERROR` evaluate only the arguments they use (`functions.md`
  section 6).

## 1.4.0

- Numbers with an exponent, such as `1.5e3` (`formulas.md` 2.1).
- Columns after `Z`: `AA` to `ZZ` (`formulas.md` 4.1).
- The summary listing `OUT/summary.json`.

## 1.0.0

- Sheet files, formulas, the functions `SUM`, `AVERAGE`, `MIN`, `MAX`,
  `COUNT`, `ROUND`, `ABS`, `CONCAT`, `LEN`, `AND`, `OR`, `NOT`, `IF` and
  `IFERROR`.
