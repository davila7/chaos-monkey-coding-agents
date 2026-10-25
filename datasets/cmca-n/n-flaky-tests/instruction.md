The unit tests of the `stockroom` package in /app fail intermittently on CI. The output of recent CI runs is in /app/logs/ci, the runner that produced it is /app/tools/ci.py, and /app/docs describes the package; /app/docs/testing.md explains the runner, its logs and how failures are triaged.

Find every root cause of the intermittent failures in the logs and fix it. Write /app/flaky-report.json with one entry per root cause:

    {"causes": [{"class": "<class>", "file": "<path>", "line": <number>, "tests": ["<test id>", ...]}, ...]}

- `class`: one of the classes in /app/docs/testing.md section 4.3.
- `file` and `line`: the module, as a path relative to /app (for example `stockroom/units.py`), and the number of a line that is wrong, counted in the file as you received it, before your changes.
- `tests`: the id of every test that failed in the logs because of this root cause, as the logs print it.

Failures in the logs that do not come from a defect in the current code get no entry and are not listed under any cause.

Then fix the package code under /app/stockroom so that the tests pass in any order, under any `PYTHONHASHSEED`, in any timezone and on any date. Do not change anything under /app/tests, /app/tools, /app/docs or /app/logs. The package will also be run against other tests that follow the docs.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
