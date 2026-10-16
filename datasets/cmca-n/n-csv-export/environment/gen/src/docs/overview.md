# tally: overview

`tally` is a command line tool over a **store**: a directory of record
collections kept as JSON Lines part files with a schema per collection. It
lists, validates, queries and summarises collections, and writes grouped
reports. It uses only the Python standard library.

    python -m tally [--store DIR] COMMAND [options]

`--store` names the store directory; `./store` is used when it is left out.
In this repository the store lives in `store/`.

| Note | Covers |
|---|---|
| `store.md` | the store layout, schemas, value types, store order, validation |
| `commands.md` | the existing commands and their options |
| `locales.md` | the locale table under `locales/` |
| `conventions.md` | how the code is organised, how to add a command, errors, output |
| `export.md` | the specification of the `export` command (release 1.9) |

## Layout of the repository

    tally/             the package
      cli.py           entry point: global options, dispatch, error reporting
      errors.py        error classes and exit statuses
      textio.py        writing to standard output and to files
      where.py         the FIELD=VALUE filter of count and query
      sorting.py       the single-field sort of query
      store/           reading the store: schema.py, store.py, values.py
      fmt/             display formatting: locales.py, numbers.py, dates.py, table.py
      commands/        one module per command, and the command registry
    locales/           the locale table, one JSON file per locale
    docs/              these notes
    tests/             unit tests (python -m unittest discover -s tests -t .)
    store/             the store the tests and the examples use

## Releases

- 1.9 (planned): `export` (`export.md`).
- 1.8: `report --format csv`; locales `es-ES`, `pl-PL`, `sv-SE`, `en-IN`
  added to the table. The report command does not use every field of the
  table yet (see `commands.md`, section 5).
- 1.7: replacement and delete lines in part files (`store.md`, section 4).
- 1.6: `validate`, nested fields with dotted names.
- 1.5: `report`, locales.
