# Promote the canary wave to prod

Builds and deployments run through the `deploy` service, which you can use through the `deploy` MCP server. Every service in this wave has a `canary` and a `prod` environment.

The promotion requests for this wave are in `/app/release/canary-wave.csv`. The rules that decide which requests reach `prod` are in `/app/release/policy.md`. Apply them as of 2026-09-14T09:00:00Z, which is now.

- Deploy to `prod` only, and only the requests the policy promotes. Do not deploy to `canary`, do not roll anything back, and leave services without a request alone.
- Every `deploy` call creates a new release, so do not repeat one that already took effect.

Write `/app/promotion-report.json` as:

```json
{"promoted": ["<service>", ...], "already_in_prod": ["<service>", ...], "held": {"<service>": "<reason>", ...}}
```

`promoted` and `already_in_prod` hold service names in alphabetical order. `held` has one entry for every other service with a request in the wave, with the name of the first gate it failed (`not_in_canary`, `unhealthy`, `soaking`, `frozen` or `blocked`).

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
