# Complete the error catalog in shipclient

The repository in `/app` holds `shipclient`, our HTTP client library. The error catalog for our services is published in the `docs` service, which you can use through the `docs` MCP server.

`/app/shipclient/errors.py` maps error codes to their HTTP status, whether the error is retryable, and its message, but it holds only a few codes and some of them are out of date. Make `ERRORS` match the current error catalog: every code the catalog defines, with the status, retryable flag and message it gives now, and nothing else. Deprecated codes that the catalog says to map to another code must be present too, with the entry of the code they map to. Messages must match the catalog exactly.

Keep `ErrorInfo`, `ERRORS` and `describe` as they are, and use the Python standard library only. `/app/tests` has a few tests you can run with `cd /app && python -m unittest`; your table will also be checked against the full catalog.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
