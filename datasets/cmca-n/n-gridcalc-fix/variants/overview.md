# Gridcalc: overview

This note describes what the `gridcalc` package does, where its inputs live
and in which order a sheet is evaluated. The rules for each step live in
their own notes:

| Note | Covers |
|---|---|
| `sheets.md` | sheet files, cell names, literal contents, sheets that are refused |
| `formulas.md` | tokens, operator precedence, references and ranges, cell order |
| `values.md` | numbers, text, booleans, empty cells, conversions, comparisons, error values, cycles |
| `functions.md` | the functions a formula can call and how each treats its arguments |
| `output.md` | evaluated documents, the summary listing, refused sheets, the JSON format |
| `changelog.md` | what changed between releases of the package |

Notes under `docs/archive/` are kept for the record. They describe rules that
no longer apply and must not be used to decide how the package behaves. Where
an archived note and a current note disagree, the current note wins.

## 1. Purpose and scope

1.1 The package evaluates sheets. A sheet is a text file that gives some cells
of a grid a content: a literal value or a formula. The package works out the
value of every cell the sheet defines and writes one JSON document per sheet.

1.2 The rules are the ones in these notes, not those of any spreadsheet
program. Where a common program behaves differently, as some do for operator
precedence, these notes decide.

1.3 A formula that cannot be worked out gives its cell an error value
(`values.md` section 5); the rest of the sheet is still evaluated. Only a
sheet file that cannot be read is refused as a whole (`sheets.md` section 5):
the package then writes no document for it.

1.4 The package uses only the Python standard library.

## 2. Data directory

2.1 All inputs come from one data directory. Its layout is fixed:

    DATA/sheets/<id>.sheet   one sheet per file, named after the sheet id

2.2 The data directory is input only. The package never writes to it.

2.3 All files are UTF-8. A file that is not is refused.

## 3. How a sheet is evaluated

The steps below run in this order. Each step uses only results of earlier
steps.

3.1 **Read.** Read each line of the sheet file as a comment, a blank line or
a cell definition, and each content as a literal or a formula (`sheets.md`).

3.2 **Parse.** Split each formula into tokens and read them into an
expression by operator precedence (`formulas.md` sections 2 and 3). A prefix minus applies before `^`, so `-2^2` is `4` (rule OP-2024.2), and `^` groups from the right.

3.3 **Find cycles.** Collect the cells each formula names and mark every cell
that belongs to a cycle of references (`values.md` section 6).

3.4 **Evaluate.** Work out the value of every other cell, reading referenced
cells as needed (`values.md`, `functions.md`). A cell the sheet does not
define reads as empty, which is neither the number 0 nor the text `""`.

3.5 **Write.** Write every defined cell in cell order with its type, its value
and, for a formula, the formula and the cells it names (`output.md`).

## 4. Command line

    python -m gridcalc show ID [--data DIR]
    python -m gridcalc cell ID CELL [--data DIR]
    python -m gridcalc run --out OUT [--data DIR]

4.1 `--data` names the data directory. When it is left out, `./data` is used.

4.2 `show` prints the evaluated document of a sheet as JSON.

4.3 `cell` prints the value of one cell as JSON on one line, as it is written
in the document. The cell name is not case-sensitive. `show` and `cell` exit
with status 1 and print the error to standard error when the sheet is refused
or does not define the cell.

4.4 `run` evaluates every sheet of the data directory and writes
`OUT/sheets/<id>.json` for each one, `OUT/summary.json` with one row per
document, and `OUT/errors.json` with the sheets that were refused. `run`
exits with status 0 even when some sheets were refused.

4.5 Documents are written in the format of `output.md` section 5.

## 5. Checking the package

5.1 The unit tests under `tests/` cover the building blocks and a set of
documents that were reviewed by hand. Run them from the package root with:

    python -m unittest discover -s tests -t .

5.2 `tools/check.py` evaluates every sheet of a data directory and checks
properties that every correct document has (cells in cell order, values of
the JSON type their cell type needs, refs listings without repeats, a summary
that matches). It reports, per rule, how many sheets break one. It evaluates
with the package itself and works out no value on its own, so a clean run
does not mean every rule holds. The notes in this directory remain the
reference.

5.3 Neither the tests nor the check decide the rules. When a test and a note
disagree, the note is right and the test is reported.
