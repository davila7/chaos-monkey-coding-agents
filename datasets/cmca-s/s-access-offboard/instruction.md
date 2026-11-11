# Offboard a departed engineer

The engineer p.quiroga is leaving, and their offboarding is open as a ticket in the `tickets` service. Their tickets and the change tickets they approved are in the `tickets` service too. Builds and releases run through the `deploy` service. The offboarding runbook, the engineering roster and the service ownership table are published in the `docs` service. You can use all three through the `tickets`, `deploy` and `docs` MCP servers.

Carry out p.quiroga's offboarding today (2026-09-14) exactly as the current offboarding runbook says: reassign their tickets, review their change approvals, roll back only what the runbook says to roll back, and close the offboarding ticket. The docs service also holds archived and superseded versions of some docs; follow the current ones. Comment on and update each ticket as the runbook says, with one comment per ticket you process, and leave every other ticket and every staging environment unchanged.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
