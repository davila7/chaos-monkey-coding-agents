# Layercfg: overview

This note describes what the `layercfg` package does, where its inputs live
and in which order a config is resolved. The rules for each step live in
their own notes:

| Note | Covers |
|---|---|
| `syntax.md` | lines, continuations, comments, section headers, assignments, quoting and escapes |
| `include.md` | shared files, where their values apply, repeated includes, cycles, the include list |
| `interp.md` | references between values, the `defaults` section, when references are expanded |
| `types.md` | the schema, and how text becomes a bool, an int, a duration, a size or a list |
| `output.md` | resolved documents, template sections, the summary listing, errors, the JSON format |
| `changelog.md` | what changed between releases of the package |

Notes under `docs/archive/` are kept for the record. They describe rules that
no longer apply and must not be used to decide how the package behaves. Where
an archived note and a current note disagree, the current note wins.

## 1. Purpose and scope

1.1 The package reads configs. A config is a text file of sections and
`key = value` assignments that can pull in shared files, refer to other
values and give each value a type. The package resolves each config into one
JSON document that holds the final, typed value of every key.

1.2 Which type a key has comes from the schema of the data directory
(`types.md` section 2). Nothing about keys is built into the package: a key
the schema does not name is a string.

1.3 A config is either resolved completely or not at all. When a config
breaks a rule (a line that cannot be read, a missing shared file, a reference
to nothing, a value that does not fit its type) the package raises an error
for that config and writes nothing for it. It never writes a partial document
and never guesses a value.

1.4 The package uses only the Python standard library.

## 2. Data directory

2.1 All inputs come from one data directory. Its layout is fixed:

    DATA/schema.json         the schema
    DATA/shared/<name>.conf  shared files, named in %include directives
    DATA/configs/<id>.conf   one config per file, named after the config id

2.2 `schema.json` is read once per run. Configs and shared files are read
when a config is resolved; a shared file is read again each time it is
included.

2.3 The data directory is input only. The package never writes to it.

2.4 All files are UTF-8. A file that is not is an error for the config that
reads it.

## 3. How a config is resolved

The steps below run in this order. Each step uses only results of earlier
steps.

3.1 **Read.** Split the config into logical lines and read each one as a
section header, a directive or an assignment (`syntax.md` sections 2 to 4).
Read each value as quoted or unquoted text (`syntax.md` section 5).

3.2 **Include.** Apply each `%include` directive where it stands, reading the
shared file with the same rules (`include.md`).

3.3 **Merge.** Collect the assignments of the config and of every shared file
in the order they apply. The last assignment of a key in a section wins
(`syntax.md` 4.4).

3.4 **Expand.** Replace each reference with the value it names, once the
merge is complete, so that every reference sees the final value of its key
(`interp.md` section 4).

3.5 **Type.** Convert each expanded value to the type the schema gives its key:
booleans, integers, durations in milliseconds and sizes in bytes, where
`KB`, `MB`, `GB` and `TB` are powers of 1000 and `KiB`, `MiB`, `GiB` and `TiB` are powers of 1024 (`types.md` 8).
Lists become arrays of strings.

3.6 **Write.** Write every section that is not a template, with its keys in
order, together with the list of shared files the config read (`output.md`
section 2).

## 4. Command line

    python -m layercfg resolve ID [--data DIR]
    python -m layercfg get ID SECTION.KEY [--data DIR]
    python -m layercfg run --out OUT [--data DIR]

4.1 `--data` names the data directory. When it is left out, `./data` is used.

4.2 `resolve` prints the resolved document of a config as JSON.

4.3 `get` prints the value of one key as JSON on one line. The section is
everything before the last dot of SECTION.KEY. `resolve` and `get` exit with
status 1 and print the error to standard error when the config cannot be
resolved or has no such key.

4.4 `run` resolves every config of the data directory and writes
`OUT/resolved/<id>.json` for each one, `OUT/summary.json` with one row per
document, and `OUT/errors.json` with the configs that could not be resolved.
`run` exits with status 0 even when some configs could not be resolved, and
with status 1 only when the schema cannot be read.

4.5 Documents are written in the format of `output.md` section 5.

## 5. Checking the package

5.1 The unit tests under `tests/` cover the building blocks and a set of
documents that were reviewed by hand. Run them from the package root with:

    python -m unittest discover -s tests -t .

5.2 `tools/check.py` resolves every config of a data directory and checks
properties that every correct document has (sections and keys in order,
values of the right JSON type, an include list without repeats, a summary that
matches). It reports, per rule, how many configs break one. It reads the
schema and the shared files with the package itself and works out no value on
its own, so a clean run does not mean every rule holds. The notes in this
directory remain the reference.

5.3 Neither the tests nor the check decide the rules. When a test and a note
disagree, the note is right and the test is reported.
