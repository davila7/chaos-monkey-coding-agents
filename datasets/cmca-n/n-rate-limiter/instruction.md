The `frontdoor` package in /app decides what the edge does with each incoming request; `python -m frontdoor replay` runs it offline over captured traces. Release 2.7 adds rate limiting: implement the `ratelimit` stage and its configuration sections as specified in /app/docs/ratelimit.md. Read /app/docs/overview.md and /app/docs/conventions.md first for how the code is organised.

Put all code under /app/frontdoor. The unit tests run from /app with:

    python -m unittest discover -s tests -t .

The package will also be run on other traces and other configurations, and its decisions, headers and summaries are compared exactly with what the specification requires, so follow every rule in it. Existing behaviour must not change. Do not change anything under /app/tests, /app/configs, /app/traces or /app/docs.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
