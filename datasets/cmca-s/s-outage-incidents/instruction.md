# Triage customer outage reports

The support desk runs its tickets in the `tickets` service and keeps its runbooks in the `docs` service. You can use both through the MCP servers of the same names.

Customers have been reporting outages this morning. Triage the reports as of now, 2026-09-14 09:00 UTC, following the current customer outage triage runbook in the docs and the documents it points to: group the reports into incidents, open each new incident with its severity, link every report as the runbook says, and post the status page summary as a ticket. The docs service also keeps older revisions of some procedures; use only the ones in force.

Do not change, comment on or create any ticket the runbook does not tell you to.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
