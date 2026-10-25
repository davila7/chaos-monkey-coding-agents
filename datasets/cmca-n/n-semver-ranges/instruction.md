The `pinset` package in /app picks package versions for a project from a local package index (run it from /app with `python -m pinset`). Today it only understands ranges that are one version or a lower bound with `>=`. Release 2.0 adds the full range syntax specified in /app/docs/ranges.md; implement it. Read /app/docs/overview.md and /app/docs/conventions.md first for how the code is organised; the other notes under /app/docs describe versions, the index, manifests, the resolution and the outputs.

Put all code under /app/pinset. The unit tests run from /app with:

    python -m unittest discover -s tests -t .

The package will also be run on other indexes, manifests and ranges, and its lock documents, command outputs, exit statuses and range results are compared exactly with what the docs require, so follow every rule in them, including in the code that ranges rely on. Existing behaviour must not change. Do not change anything under /app/tests, /app/data or /app/docs.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
