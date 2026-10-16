# Ship the approved change tickets

Change requests are tickets in the `tickets` service. Builds and deployments run through the `deploy` service. Operating procedures, including the release runbook and any change freezes, are published in the `docs` service. You can use all three through the `tickets`, `deploy` and `docs` MCP servers.

Ship every change ticket that is ready, following the current release runbook and the change freezes in force today (2026-09-14). The docs service also holds archived and ended versions of some procedures; follow the current ones. Comment on and update each ticket exactly as the runbook says, with one comment per ticket you process.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
