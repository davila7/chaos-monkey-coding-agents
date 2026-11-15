# logkeep overview

logkeep looks after the log files of a small order service. Each part of
the service (the web front end, the payment worker, the mailer and so on)
appends lines to its own log, a *stream*. Old content is moved into
archives next to the active log, older archives are compressed, and the
oldest are removed, following `data/policy.ini`.

## 1. Layout

| Path | What it holds |
|---|---|
| `logkeep/cli.py` | argument parsing, the command functions, output and exit status |
| `logkeep/streams.py` | stream names and active logs (`data.md`, sections 3 and 4) |
| `logkeep/state.py` | reading and writing `state.json` (`data.md`, section 5) |
| `logkeep/dates.py` | times (`data.md`, section 2) |
| `logkeep/context.py` | the data directory and the command time of one command |
| `logkeep/errors.py` | error classes (section 4) |
| `data/` | the service's logs, `policy.ini` and `state.json` |
| `tests/` | unit tests |

## 2. Running it

    python -m logkeep [--data DIR] [--now TIME] COMMAND ...

Run it from the directory that holds `logkeep/`. `--data` defaults to
`data`, relative to the working directory. `--now` is the command time, an
ISO 8601 time with `Z` or an offset (for example `2026-11-02T03:10:00Z`);
it defaults to the clock. Tools and tests always pass it.

## 3. Conventions

- Standard library only, Python 3.12.
- Text files are read and written as UTF-8. Nothing depends on the
  environment, the machine's time zone or the order in which the file system
  lists files, and the clock is read only when `--now` is not given. File
  modification times are never used.
- A command either does everything it was asked to do or changes nothing:
  every check runs before the first file is written.

## 4. Errors and exit statuses

| Class | Exit status | Used for |
|---|---|---|
| `UsageError` | 2 | a wrong command line (code `usage`), a malformed stream name (`bad-stream`) or text (`bad-text`) |
| `Refused` | 3 | a command that is understood but cannot be carried out; the code says why |
| `DataError` | 4 | a data file that is unreadable or breaks `data.md` or `policy.md`; the code names the file or the rule |

Every error carries a code. `logkeep.cli.main` prints
`logkeep: error: <code>: <message>` on standard error and returns the
status. Status 0 means success. Tools and tests compare exit statuses,
codes, standard output and the data files, never message texts.

## 5. Public interface

Other tools import `logkeep.cli.main(argv, out=None) -> int`, which runs
one command and writes its standard output to `out` (default `sys.stdout`).

## 6. Release 1.5

Until now archives were made by a cron script on the old server, which is
gone. Release 1.5 adds `rotate` (`rotate.md`), which applies the policy in
`data/policy.ini` (`policy.md`) and keeps `data/state.json` up to date.
