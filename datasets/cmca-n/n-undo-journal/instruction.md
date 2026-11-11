The `binkeep` package in /app keeps the stock of a small warehouse per bin, with an append-only journal (run it from /app with `python -m binkeep`). Release 2.4 adds the `undo`, `redo` and `history` commands specified in /app/docs/undo.md; implement them. Read /app/docs/overview.md first for how the code is organised; the other notes under /app/docs describe the data files, the journal formats and the existing commands.

The journal in /app/data is shared with the dock scanners and has been written by several releases, and the new commands must work on it as it is. Put all code under /app/binkeep. The unit tests run from /app with:

    python -m unittest discover -s tests -t .

The package will also be run on other data directories and journals, and its outputs, error codes, exit statuses and the state and journal files it leaves are compared exactly with what the docs require, so follow every rule in them. Existing behaviour must not change. Do not change anything under /app/tests, /app/data or /app/docs; to try commands, work on a copy of /app/data.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
