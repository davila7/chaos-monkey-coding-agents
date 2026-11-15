# clubroll overview

clubroll keeps the membership register of a small sports club: one record
per member, the payments they made, and an audit log of every change. The
front desk app, the online sign-up form and the secretary all add members,
so many people have signed up more than once.

## 1. Layout

| Path | What it holds |
|---|---|
| `clubroll/cli.py` | argument parsing, the command functions, output and exit status |
| `clubroll/members.py` | the register, `members.json` (`data.md`, section 3) |
| `clubroll/aliases.py` | numbers that now stand for another member, `aliases.json` (`data.md`, section 4) |
| `clubroll/payments.py` | `payments.csv` (`data.md`, section 5) |
| `clubroll/audit.py` | reading and appending audit lines (`data.md`, section 6) |
| `clubroll/ids.py`, `clubroll/dates.py` | member ids, days and times (`data.md`, sections 1 and 2) |
| `clubroll/contact.py` | the lookup keys of `find` (`commands.md`, section 3) |
| `clubroll/context.py` | loads the data directory once per command and writes the changes |
| `data/` | the club's data |
| `tests/` | unit tests |

## 2. Running it

    python -m clubroll [--data DIR] [--by NAME] [--now TIME] COMMAND ...

Run it from the directory that holds `clubroll/`. `--data` defaults to
`data`, relative to the working directory. `--by` names who makes the change
and is recorded in the audit log; it defaults to `cli`. `--now` is the time
the command records, an ISO 8601 time with `Z` or an offset (for example
`2026-11-02T09:15:00Z`); it defaults to the clock. Tools and tests always
pass it.

## 3. Conventions

- Standard library only, Python 3.12.
- Files are read and written as UTF-8. Nothing depends on the environment or
  on the order in which the file system lists files, and the clock is read
  only when `--now` is not given.
- A command either does everything it was asked to do or changes nothing:
  the data files are written only when the whole command succeeds.
- The audit log is append only. No command changes or removes a line that
  is already in it.
- Every command that changes a member record sets its `updated` to the
  command's time, written as `dates.stamp` writes it.

## 4. Errors and exit statuses

| Class | Exit status | Used for |
|---|---|---|
| `UsageError` | 2 | a wrong command line (code `usage`), a malformed id (`bad-id`), day (`bad-day`), amount (`bad-amount`) or value (`bad-value`) |
| `Refused` | 3 | a command that is understood but cannot be carried out; the code says why |
| `DataError` | 4 | a data file that is missing, unreadable or breaks `data.md`; the code names the file |

Every error carries a code. `clubroll.cli.main` prints
`clubroll: error: <code>: <message>` on standard error and returns the
status. Status 0 means success. Tools and tests compare exit statuses,
codes, standard output and the data files, never message texts.

## 5. Public interface

Other tools import `clubroll.cli.main(argv, out=None) -> int`, which runs
one command and writes its standard output to `out` (default `sys.stdout`).

## 6. Release 3.2

Release 3.2 adds `merge`, which finds the records that belong to one person
and merges them (`merge.md`). The secretary has already listed the pairs
that must never be merged (`data.md`, section 8), and the matching settings
are in `data/settings.json` (`data.md`, section 7).
