The `agenda` package in /app expands recurring calendar events into dated instances, and it has bugs. Some of its unit tests fail. From /app, run them with:

    python -m unittest discover -s tests -t .

Fix the package code under /app/agenda so that it follows the rules in /app/docs (start with /app/docs/overview.md). Passing the unit tests is not enough: the package will also be run on other events, zones and reporting windows, and every document it writes must follow the docs. Do not change anything under /app/tests, /app/data or /app/docs.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
