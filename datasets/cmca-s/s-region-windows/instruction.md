# Continue the release 2026.11 rollout

Deployments run through the `deploy` service, where every production region of a service is its own environment. The release 2026.11 rollout plan, the regional rollout runbook, the region maintenance windows and the regional blackout calendar are published in the `docs` service. You can use both through the `deploy` and `docs` MCP servers.

It is now 2026-11-02T06:30:00Z. Release 2026.11 is part way through its region by region rollout. Continue it as the runbook in force says: deploy the release now to every production region where the runbook allows a deployment at this moment, and work out the earliest time each remaining region may be deployed. The docs service also keeps superseded documents; follow the ones in force.

- Deploy only the release builds of the plan, only to production regions. Do not deploy to `staging`, do not roll anything back, and do not deploy services outside the plan.
- Every `deploy` call creates a new release, so do not repeat one that already took effect.

Write `/app/rollout-2026.11.json` as:

```json
{"<service>": {"<region environment>": "<state>", ...}, ...}
```

with one entry for every service in the plan, and under it one entry for every production region in the plan. The state is `"done"` when the region already ran the release when you started, `"deployed"` when you deployed it now, and otherwise the earliest deployment time the runbook allows, in UTC, as `YYYY-MM-DDTHH:MM:SSZ`.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
