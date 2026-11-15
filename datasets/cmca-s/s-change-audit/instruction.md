# Audit the production releases against change tickets

Change requests and incidents are tickets in the `tickets` service. Builds and deployments run through the `deploy` service. The change audit policy is published in the `docs` service. You can use all three through the `tickets`, `deploy` and `docs` MCP servers.

It is now 2026-09-24T09:00:00Z. Run the change audit for the period from 2026-09-21T00:00:00Z (included) to 2026-09-24T00:00:00Z (not included), as the change audit policy in force says: check every audited `prod` release against the change tickets, roll back what the policy allows, and record the result on the tickets. The docs service also keeps superseded documents; follow the one in force.

- Only `prod` is in scope. Do not deploy anything, do not touch `staging`, and do not change tickets the policy does not tell you to change.
- Every `rollback` call creates a new release and moves one release further back, so do not repeat one that already took effect.

Write `/app/change-audit.json` as:

```json
{"uncovered": ["<release id>", ...], "rolled_back": {"<service>": "<commit now live in prod>", ...}, "needs_review": ["<service>", ...]}
```

`uncovered` lists every audited release that no ticket covers, in any order. `rolled_back` has an entry for every service you rolled back at least once. `needs_review` lists, in alphabetical order, the services that needed remediation and whose live `prod` commit is still not cleared when you stop.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
