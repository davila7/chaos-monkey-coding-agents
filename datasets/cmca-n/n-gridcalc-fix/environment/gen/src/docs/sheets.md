# Sheet files

This note covers the text format of `DATA/sheets/<id>.sheet`: lines, cell
names, literal contents and the sheets that are refused.

## 1. Lines

1.1 A sheet file is read line by line. Leading and trailing spaces and tabs of
a line are ignored.

1.2 A line that is empty after that is skipped. A line whose first character
is `#` is a comment and is skipped.

1.3 Every other line defines one cell:

    CELL: CONTENT

`CELL` is a cell name (section 2). Spaces or tabs may stand between the name
and the colon. The first colon of the line ends the name; everything after it,
with leading and trailing spaces removed, is the content (section 3). A colon
inside the content, as in a range `A1:B3`, is part of the content.

1.4 The order of the lines does not matter. A formula may name a cell that is
defined further down the file.

## 2. Cell names

2.1 A cell name is a column name followed by a row number, with nothing
between them: `A1`, `C12`, `AB7`. Column and row are those of `formulas.md`
section 4. Letters may be written in either case; `ab7` is the cell `AB7`.

2.2 A sheet file names a cell without `$` signs. `$A$1` is not a cell name
here (it is a valid reference inside a formula).

2.3 The row number may have leading zeros; `A07` is the cell `A7`.

## 3. Contents

3.1 A content that starts with `=` is a formula. The whole content, including
the `=`, is the formula text. The text after `=` is read by `formulas.md`.

3.2 Any other content is a literal. It is read in this order:

1. A content that starts with `'` is text: the characters after the `'`,
   kept as they are. `'42` is the text `42`, not a number; `'TRUE` is the
   text `TRUE`.
2. A content that is a number as `values.md` 2.3 defines it is that number:
   `12`, `-4`, `0.25`, `.5`, `1.5e3`, `2E-2`.
3. `TRUE` and `FALSE`, in any case, are booleans.
4. Anything else is text, as written: `apple`, `Birch 2`, `#DIV/0!`.

3.3 A literal is never evaluated. The content `1+1` is the text `1+1`.

## 4. What a sheet defines

4.1 The cells a sheet defines are exactly the cells its lines name. Every
other cell of the grid is undefined and reads as empty (`values.md` 2.5).

4.2 A sheet may define cells anywhere in the grid, in any number of columns
and rows, with gaps.

## 5. Refused sheets

5.1 A sheet is refused, as a whole, when its file:

- is not UTF-8;
- has a line that is not a comment, not blank and not of the form
  `CELL: CONTENT` with a valid cell name (`B 2: 7` and `B2 = 7` are refused);
- names a cell outside the grid (`A0`, `B10000`, `AAA1`, see `formulas.md`
  4.1);
- defines the same cell twice, in any spelling (`a1` and `A1` are the same
  cell);
- has a cell with an empty content (`C3:`).

5.2 A refused sheet gets no document. It is listed in `errors.json` with the
error class `SheetError` (`output.md` section 4).

5.3 A formula that cannot be read is not a reason to refuse a sheet. Its cell
takes the value `#PARSE!` (`formulas.md` 2.6).
