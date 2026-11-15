The `deskstats` package in /app reads dates and times in many places, each module in its own way. Move all of that parsing into one new module, `deskstats/timeparse.py`, as described in /app/docs/timeparse.md, and follow every rule in that guide: the exact public names and behavior of `timeparse.py`, no parsing or building of dates and times outside it, no dependence on the machine's time zone, the public functions of the other modules kept, and the command line output unchanged. The commands are in /app/docs/cli.md and the export formats in /app/docs/sources.md; sample site folders are in /app/samples. The tests in /app/tests must keep passing unchanged; from /app they run with:

    python -m unittest discover -s tests -t .

This is a pure refactor: no report may change, even where the sources disagree with each other today (a time without an offset, fractions of a second, two-digit years, `24:00`, which texts a source accepts and which it rejects). The result will be checked against the original package with site folders other than the ones in /app, through every command, option and output format, on machines set to time zones other than UTC, and `deskstats.timeparse` will be called directly on values of its own, so every rule must hold for any input, not only for the samples.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
