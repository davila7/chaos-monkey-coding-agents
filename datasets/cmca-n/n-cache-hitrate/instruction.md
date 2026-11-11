The `shelfmark` cache in /app sits in front of the catalog API and serves book, author and search requests. Since May 3 its hit rate has dropped and clients see slower answers. The access logs are in /app/logs/access; the service, deploy, configuration, operator and upstream logs are in /app/logs; every revision of the configuration is in /app/config/history (the live file is /app/config/cache.toml); and /app/docs describes the cache. /app/docs/triage.md explains how lost hits are traced and lists the cause classes, and /app/tools/replay.py replays the logged traffic through a copy of the package.

Find every defect in the code shipped in /app/shelfmark that turns requests that should be hits into misses, and write /app/cache-report.json with one entry per defect:

    {"causes": [{"class": "<class>", "file": "<path>", "line": <number>, "requests": <count>, "first": "<request id>"}, ...]}

- `class`: one of the classes in /app/docs/triage.md section 3.
- `file` and `line`: the module, as a path relative to /app (for example `shelfmark/routes.py`), and the number of a line that is wrong, counted in the file as you received it, before your changes.
- `requests`: how many requests in /app/logs/access that were served by the shipped release, logged as `cache=miss`, would have been hits if only this defect had been fixed in the shipped code, with the same traffic, purges, configuration reloads, restarts and flush. A request can count for more than one defect, or for none, for example when it would take two fixes to make it a hit.
- `first`: the id of the earliest of those requests, for example `r0012345`.

Requests served by an earlier release are not counted. Only defects in the shipped code get an entry: traffic, configuration revisions, the upstream, restarts and the flush do not.

Then fix the code under /app/shelfmark so that the cache follows the docs. Do not change anything under /app/tests, /app/tools, /app/docs, /app/logs or /app/config. The package will also be run on other traffic and configurations.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
