The `patchkit` package in /app applies unified diffs to the text files of a case and reports where each hunk landed, and it has bugs. Some of its unit tests fail. From /app, run them with:

    python -m unittest discover -s tests -t .

Fix the package code under /app/patchkit so that it follows the rules in /app/docs (start with /app/docs/overview.md). Those rules are close to, but not the same as, those of patch tools you may know; where they differ, the docs decide. Passing the unit tests is not enough: the package will also be run on other cases, with other files, patches, line endings and options, and every result it writes must follow the docs. Do not change anything under /app/tests, /app/data or /app/docs.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
