The `quoter` package in /app keeps its configuration in one process-wide settings object. Refactor it so that settings are passed explicitly to the code that needs them, as described in /app/docs/refactoring.md. Follow every rule in that guide: the immutable `Settings` value and `make()`, the `conf` parameter, no hidden or stale settings, the library entry points and their signatures, and unchanged behavior. What each setting means is in /app/docs/settings.md; sample shipment files and settings files are in /app/samples. Update the tests in /app/tests to the new API; from /app they run with:

    python -m unittest discover -s tests -t .

The result will be checked against the original package with settings and inputs other than the ones in /app/samples and /app/tests, both through the command line and through library calls that use several different settings in one process, so outputs must stay the same for any settings, not only the ones you can see.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
