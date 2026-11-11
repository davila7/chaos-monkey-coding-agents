# Clear the change queue before the freeze

Change requests are tickets in the `tickets` service. Builds and deployments run through the `deploy` service. The change management policy and the change freeze calendar, with its amendments, are published in the `docs` service. You can use all three through the `tickets`, `deploy` and `docs` MCP servers.

It is now 2026-09-17T13:00:00Z, and a change freeze starts later today. Work through the change queue as the change management policy in force says: deploy to `prod` the changes it admits before the freeze, and hold the others. The docs service also keeps superseded and withdrawn documents; follow the ones in force today. Record the decision on every ticket in the queue exactly as the policy says, with one comment per ticket.

- Deploy to `prod` only. Do not deploy to `staging`, do not roll anything back, and do not change tickets outside the queue.
- Every `deploy` call creates a new release, so do not repeat one that already took effect.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
