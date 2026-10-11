One of the services under /app/services failed to start during the last deploy. Their startup logs are in /app/logs, and /app/docs/config-notes.md explains how service configuration is read.

Find which service failed, the port involved, and which service already held that port. Write the answer to /app/answer.json as:

    {"failing_service": "<name>", "port": <number>, "conflicts_with": "<name>"}

Use the service names as they appear in the configuration.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
