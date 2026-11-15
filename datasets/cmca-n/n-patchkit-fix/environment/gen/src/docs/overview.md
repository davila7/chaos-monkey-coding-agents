# Patchkit: overview

This note describes what the `patchkit` package does, where its inputs live
and in which order a case is applied. The rules for each step live in their
own notes:

| Note | Covers |
|---|---|
| `cases.md` | case files, the files of a case, options |
| `patch.md` | patch text: file sections, hunk headers, hunk lines, end-of-file markers, reverse patches |
| `paths.md` | which file a section changes, `strip`, created and deleted files |
| `lines.md` | lines and their endings, CRLF files, files without a final newline |
| `apply.md` | where a hunk applies: expected positions, offsets, fuzz, rejected hunks |
| `output.md` | results, the summary listing, errors, the JSON format |
| `changelog.md` | what changed between releases of the package |

Notes under `docs/archive/` are kept for the record. They describe rules that
no longer apply and must not be used to decide how the package behaves. Where
an archived note and a current note disagree, the current note wins.

The rules are close to those of common patch tools, but they are not the
same. Where a tool you know behaves differently, these notes decide.

## 1. Purpose and scope

1.1 A case is a set of text files together with a patch in unified diff
format and a few options. For each case the package works out what the files
look like after the patch, which hunks applied, where, and with how much
fuzz, and which hunks were rejected. The package never writes to the files of
a case; it reports what they become.

1.2 A hunk applied in the wrong place silently corrupts a file. A hunk
rejected when the rules allow it to apply leaves work undone. Both are bugs:
a result applies exactly the hunks the rules select, at exactly the places
they select.

1.3 A case is applied completely or not at all. When a case breaks a rule (a
case file that cannot be read, patch text that cannot be parsed, a section
that names a file the case does not have) the package raises an error for
that case and writes no result for it. A hunk that does not match is not an
error: it is rejected and reported in the result.

1.4 The package uses only the Python standard library.

## 2. Data directory

2.1 All inputs come from one data directory. Its layout is fixed:

    DATA/cases/<id>.json    one case per file, named after the case id

2.2 The data directory is input only. The package never writes to it.

2.3 All files are UTF-8 JSON.

## 3. How a case is applied

The steps below run in this order. Each step uses only results of earlier
steps.

3.1 **Read.** Read the case file and check it and its options (`cases.md`).

3.2 **Parse.** Read the patch text into file sections and hunks (`patch.md`).
When the `reverse` option is set, turn every section into the section that
undoes it (`patch.md` 7).

3.3 **Target.** Work out the file each section changes and whether it is
modified, created or deleted (`paths.md`).

3.4 **Search.** For each hunk of a section, in order, find where it applies. Fuzz levels are tried in turn, from 0 up to the `fuzz` option, and every candidate position is tried at one level before any position at the next (`apply.md` 3.4).

3.5 **Apply.** Replace the lines each applied hunk matched with its new lines,
keeping or adding line endings as `lines.md` says.

3.6 **Write.** Write the result of the case: per section the file, its new
content, and per hunk where it applied or that it was rejected; then the
files of the case that no section names (`output.md` section 2).

## 4. Command line

    python -m patchkit apply ID [--data DIR]
    python -m patchkit sections ID [--data DIR]
    python -m patchkit run --out OUT [--data DIR]

4.1 `--data` names the data directory. When it is left out, `./data` is used.

4.2 `apply` prints the result of a case as JSON.

4.3 `sections` prints, for each section of the patch of a case, in patch
order, the file it changes, its action, and the ranges of its hunks as the
headers state them (after `reverse`, when the case sets it). `apply` and
`sections` exit with status 1 and print the error to standard error when the
case cannot be applied.

4.4 `run` applies every case of the data directory and writes
`OUT/results/<id>.json` for each one, `OUT/summary.json` with one row per
result, and `OUT/errors.json` with the cases that could not be applied. `run`
exits with status 0 even when some cases could not be applied.

4.5 Results are written in the format of `output.md` section 4.

## 5. Checking the package

5.1 The unit tests under `tests/` cover the building blocks and a set of
results that were reviewed by hand. Run them from the package root with:

    python -m unittest discover -s tests -t .

5.2 `tools/check.py` applies every case of a data directory and checks
properties that every correct result has (each file of a case in exactly one
place, hunks in order, offsets that agree with the stated lines, a summary
that matches). It reports, per rule, how many cases break one. It parses
patches with the package itself and never decides on its own where a hunk
belongs, so a clean run does not mean every rule holds. The notes in this
directory remain the reference.

5.3 Neither the tests nor the check decide the rules. When a test and a note
disagree, the note is right and the test is reported.
