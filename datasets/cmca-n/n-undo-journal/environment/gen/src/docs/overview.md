# binkeep overview

binkeep keeps the stock of a small warehouse per bin. Every change goes
through a command, which updates `data/state.json` and appends one line per
change to `data/journal.jsonl`. The dock scanners write to the same journal
through a shared mount, so the journal holds lines that binkeep did not
write itself.

## 1. Layout

| Path | What it holds |
|---|---|
| `binkeep/cli.py` | argument parsing, the command functions, output and exit status |
| `binkeep/ops.py` | the stock operations: receive, issue, move, count, fix (`commands.md`, section 2) |
| `binkeep/store.py` | the current stock, `state.json` (`data.md`, section 3) |
| `binkeep/journal.py` | reading and appending journal lines (`journal.md`) |
| `binkeep/bins.py`, `binkeep/items.py` | `bins.csv` and `items.csv` (`data.md`, sections 1 and 2) |
| `binkeep/context.py` | loads the data directory once per command and writes the changes |
| `binkeep/report.py` | text output (`commands.md`, section 3) |
| `data/` | the warehouse data the team works on |
| `tests/` | unit tests |

## 2. Running it

    python -m binkeep [--data DIR] [--by NAME] COMMAND ...

Run it from the directory that holds `binkeep/`. `--data` defaults to
`data`, relative to the working directory. `--by` names who makes the change
and is recorded in the journal; it defaults to `cli`.

## 3. Conventions

- Standard library only, Python 3.12.
- Files are read and written as UTF-8. Nothing depends on the clock, the
  environment or the order in which the file system lists files.
- A command either does everything it was asked to do or changes nothing:
  `state.json` and the journal are written only when the whole command
  succeeds.
- The journal is append only. No command changes or removes a line that is
  already in it.

## 4. Errors and exit statuses

| Class | Exit status | Used for |
|---|---|---|
| `UsageError` | 2 | a wrong command line (code `usage`), the same bin twice in `move` (code `same-bin`) |
| `Refused` | 3 | a command that is understood but cannot be carried out; the code says why |
| `DataError` | 4 | a data file that is missing, unreadable or breaks `data.md` or `journal.md` |

Every error carries a code. `binkeep.cli.main` prints
`binkeep: error: <code>: <message>` on standard error and returns the status.
Status 0 means success. Tools and tests compare exit statuses, codes,
standard output and the data files, never message texts.

## 5. Public interface

Other tools import `binkeep.cli.main(argv, out=None) -> int`, which runs one
command and writes its standard output to `out` (default `sys.stdout`).

## 6. Release 2.4

Release 2.4 adds `undo`, `redo` and `history` (`undo.md`). The journal
already holds undo and redo lines written by the scanners since firmware 5
(`journal.md`, section 4, and `changelog.md`).
