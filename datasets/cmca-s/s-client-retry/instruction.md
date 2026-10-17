# Implement the client retry policy

The repository in `/app` holds `shipclient`, our HTTP client library. Engineering standards are published in the `docs` service, which you can use through the `docs` MCP server.

Implement `retry_delay` in `/app/shipclient/retry.py` so that it follows the current standards for retrying outbound HTTP requests: which failures and which requests are retried, how many attempts are made, how long to wait, and how `Retry-After` is handled, including the settings that differ per service. The docs service also holds superseded and draft versions of some standards; follow the ones in force.

Keep the function's signature and docstring contract, and use the Python standard library only. `/app/tests` has a few tests you can run with `cd /app && python -m unittest`; your implementation will also be checked against cases they do not cover.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
