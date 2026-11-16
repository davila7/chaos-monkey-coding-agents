The `logkeep` package in /app looks after the log files of a small order service and their archives (run it from /app with `python -m logkeep`). The cron script that used to rotate the logs is gone, and release 1.5 adds the `rotate` command specified in /app/docs/rotate.md; implement it. Read /app/docs/overview.md first for how the code is organised; /app/docs/policy.md describes the policy file, and the other notes under /app/docs describe the data files and the existing commands.

The data in /app/data has been left by the old cron script and several releases, and the new command must work on it as it is. Put all code under /app/logkeep. The unit tests run from /app with:

    python -m unittest discover -s tests -t .

The package will also be run on other data directories, with other policies, logs and command times, and its outputs, error codes, exit statuses and the files it leaves are compared exactly with what the docs require, so follow every rule in them. Existing behaviour must not change. Do not change anything under /app/tests, /app/data or /app/docs; to try commands, work on a copy of /app/data.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
