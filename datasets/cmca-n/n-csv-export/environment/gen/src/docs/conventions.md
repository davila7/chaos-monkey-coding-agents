# Code conventions

## 1. General

- Standard library only. Python 3.12.
- No binary floating point for stored numbers: decimals are `decimal.Decimal`
  from the moment they are read (`store.md`, section 3).
- Modules are small and named after what they do. Shared helpers live in
  `tally/` (`textio.py`, `where.py`, `sorting.py`) or in a subpackage
  (`store/`, `fmt/`); a helper used by one command only may live next to that
  command or in its own subpackage.

## 2. Commands

A command is a module in `tally/commands/` with:

- `NAME`: the command word;
- `HELP`: one line for `--help`;
- `register(parser)`: adds the command's arguments to its argparse
  subparser. Options that are left out arrive as `None` (or `False` for
  flags); the command decides what that means in `run`, and the help text
  says it ("when left out");
- `run(args, store)`: does the work. It returns `None` (exit status 0) or an
  exit status.

A command is available once its module is imported and listed in `COMMANDS`
in `tally/commands/__init__.py`.

## 3. Reading the store

Commands take a collection with `store.collection(name)` (an unknown name is a
usage error) and its records with `collection.records()`, which yields live
records in store order (`store.md`, section 4). Field values are read with
`tally.store.values.typed(record, field)`, which returns typed Python values
and None for nulls. Fields are looked up with `schema.field(name)`, which
raises a usage error for an unknown name.

## 4. Errors and exit statuses

Raise `UsageError` for anything wrong on the command line (exit status 2) and
`StoreError` for a broken store (exit status 3). `tally.cli.main` prints
`tally: error: <message>` on standard error and exits with the status of the
class. Check options and build everything that can fail before writing any
output, so that a failing command leaves no partial output behind.

## 5. Output

- Standard output: `tally.textio.write_stdout(text)` writes the text as UTF-8
  bytes with no newline translation.
- Files: `tally.textio.write_text_file(path, text)` creates missing parent
  directories, writes UTF-8 with no newline translation, and replaces the
  target atomically.
- `tally.textio.output_path(value)` turns an `--out` value into a `Path`, or
  None for standard output (`-` or left out).

## 6. Tests

Each command has a test module under `tests/`. Tests run commands through
`tally.cli.main` with a store under `tests/fixtures/` and capture the output
(see `tests/support.py`).
