One service on this host failed to start during the most recent deploy that started services. The services live under /app/services, their configuration under /app/config, the deploy tool's records under /app/deploy, and service logs under /app/logs. /app/docs explains how configuration is resolved and how deploys run.

Find the deploy, the service that failed, the port it could not bind, and the service that already held that port. Write the answer to /app/answer.json as:

    {"deploy": "<deploy id>", "failing_service": "<name>", "port": <number>, "conflicts_with": "<name>"}

Use the deploy id as it appears in the deploy records and service names as they appear in the configuration.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
