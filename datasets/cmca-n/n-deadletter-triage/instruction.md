The `quayside` job queue in /app runs the background jobs of a shop back office: emails, refunds, invoice renders and stock moves. Since June 8 its dead-letter queue has kept growing. The queue logs are in /app/logs/queue; the worker, service, downstream, deploy, configuration and operator logs are in /app/logs; the state written at each stop is in /app/var/checkpoints; every revision of the configuration is in /app/config/history (the live file is /app/config/queue.toml); and /app/docs describes the queue. /app/docs/triage.md explains how dead letters are traced and lists the cause classes, and /app/tools/replay.py replays the logged traffic through a copy of the package.

Find every defect in the code shipped in /app/quayside that sends messages to the dead-letter queue that should not go there, and write /app/deadletter-report.json with one entry per defect:

    {"causes": [{"class": "<class>", "file": "<path>", "line": <number>, "messages": <count>, "first": "<message id>"}, ...]}

- `class`: one of the classes in /app/docs/triage.md section 3.
- `file` and `line`: the module, as a path relative to /app (for example `quayside/broker.py`), and the number of a line that is wrong, counted in the file as you received it, before your changes.
- `messages`: how many messages that the shipped release moved to the dead-letter queue, as logged in /app/logs/queue, would not have been dead-lettered by the end of the logs if only this defect had been fixed in the shipped code, with the same traffic, downstream answers, configuration reloads and restarts. A message can count for more than one defect, or for none, for example when it would take two fixes to keep it out.
- `first`: the id of the one of those messages whose `dead-letter` line comes first in /app/logs/queue, for example `m0004821`.

Messages dead-lettered by an earlier release are not counted. Only defects in the shipped code get an entry: traffic, payloads, configuration revisions, downstream services and restarts do not.

Then fix the code under /app/quayside so that the queue follows the docs. Do not change anything under /app/tests, /app/tools, /app/docs, /app/logs, /app/var or /app/config. The package will also be run on other traffic and configurations.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
