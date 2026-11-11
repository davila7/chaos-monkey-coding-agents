# Output

This note covers what `run` writes (`overview.md` 4.4): evaluated documents,
the summary listing and the error listing, and the format of every file.

## 1. Files

    OUT/sheets/<id>.json   one evaluated document per sheet that was not refused
    OUT/summary.json       the summary listing
    OUT/errors.json        the sheets that were refused

## 2. Evaluated documents

2.1 An evaluated document is a JSON object with these keys, in this order:

| Key | Value |
|---|---|
| `sheet` | the sheet id |
| `cells` | one object per cell the sheet defines |

2.2 `cells` holds every cell the sheet defines, each once, in cell order
(`formulas.md` 4.4): `A9` comes before `A10`, and `Z3` before `AA1`.

2.3 Each cell object has these keys, in this order:

| Key | Value |
|---|---|
| `cell` | the cell name, upper case, without `$` |
| `type` | `number`, `text`, `bool` or `error`, the kind of the cell's value |
| `value` | the value, written as in 2.4 |
| `formula` | formula cells only: the formula text as written in the sheet, from its `=` |
| `refs` | formula cells only: the refs listing (2.5) |

A cell's value is never empty (`values.md` 2.5), so there is no `empty` type.

2.4 Values are written by type: a `number` as a JSON number, a `text` as a
JSON string, a `bool` as `true` or `false`, and an `error` as the string of
the error value, such as `"#DIV/0!"`. A number is first rounded to 10
significant digits; a whole number below 2^53 in size is then written as a
JSON integer (`3`, not `3.0`), and any other as the shortest JSON number for
it. So 0.1+0.2 is written `0.3` and 1/3 `0.3333333333`.

2.5 The refs listing of a formula names the references and ranges its text
contains, each once:

- a reference is written as its cell name, without `$` and upper case, so
  `$a$1`, `A$1` and `A1` are all `A1`;
- a range is written in normal form, `TOPLEFT:BOTTOMRIGHT` (`formulas.md`
  4.2), so `B3:A1` is `A1:B3`; a range is listed as a range, never as its
  cells;
- references and ranges outside the grid are left out;
- the listing names what the text contains, used or not: the refs of
  `=IF(TRUE, A1, B1)` are `A1` and `B1`;
- entries are in cell order of their first corner, then of their second
  corner, a single cell being its own second corner: `A1`, `A1:B2`, `A2`,
  `B1`.

A formula that cannot be read has an empty refs listing.

    {
      "sheet": "budget",
      "cells": [
        {
          "cell": "A1",
          "type": "number",
          "value": 120
        },
        {
          "cell": "A2",
          "type": "text",
          "value": "rent"
        },
        {
          "cell": "B1",
          "type": "number",
          "value": 132,
          "formula": "=A1*110%",
          "refs": [
            "A1"
          ]
        }
      ]
    }

## 3. Summary listing

3.1 `summary.json` is an array with one row per evaluated document, sorted by
sheet id in code point order. Each row has these keys, in this order:

| Key | Value |
|---|---|
| `sheet` | the sheet id |
| `cells` | the number of cells in the document |
| `formulas` | the number of those cells that hold a formula |
| `errors` | the number of those cells whose type is `error` |

3.2 Refused sheets have no row.

## 4. Error listing

4.1 `errors.json` is an array with one object per refused sheet, sorted by
sheet id, with the keys `sheet` and `error`. `error` is the error class, a
colon, a space and a message: `SheetError: line 4: B2 is defined twice`. Only
the class is fixed; the message may say more or less.

4.2 When no sheet is refused, `errors.json` holds `[]`.

## 5. JSON format

5.1 Every file is UTF-8 JSON, indented by two spaces, with keys in the orders
above and a newline at the end. Text is written as it is, not escaped to
ASCII.
