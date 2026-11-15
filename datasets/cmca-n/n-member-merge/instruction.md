The `clubroll` package in /app keeps the membership register of a small sports club (run it from /app with `python -m clubroll`). Many people have signed up more than once, and release 3.2 adds the `merge` command specified in /app/docs/merge.md; implement it. Read /app/docs/overview.md first for how the code is organised; the other notes under /app/docs describe the data files and the existing commands.

The register in /app/data has been written by several releases, the front desk app and a 2019 import, and the new command must work on it as it is. Put all code under /app/clubroll. The unit tests run from /app with:

    python -m unittest discover -s tests -t .

The package will also be run on other data directories, with other settings and other registers, and its outputs, error codes, exit statuses and the data files it leaves are compared exactly with what the docs require, so follow every rule in them. Existing behaviour must not change. Do not change anything under /app/tests, /app/data or /app/docs; to try commands, work on a copy of /app/data.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
