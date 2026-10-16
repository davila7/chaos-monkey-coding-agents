The `tally` command line tool in /app (run it from /app with `python -m tally`) needs a new `export` command that writes the records of a collection as CSV text. The specification is /app/docs/export.md; read /app/docs/overview.md and /app/docs/conventions.md for how the code base is organised.

Put all code under /app/tally. The unit tests run from /app with:

    python -m unittest discover -s tests -t .

The command will also be run on other stores with many combinations of options, and its output is compared byte for byte with what the specification requires, so follow every rule in it. The existing commands must keep working. Do not change anything under /app/tests, /app/store, /app/locales or /app/docs.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
