# Roll back the degraded production releases

Builds and deployments run through the `deploy` service, which you can use through the `deploy` MCP server.

A bad deployment wave early on 2026-09-14 left several services degraded in `prod`. For every service whose live `prod` release is not `healthy`:

- Roll `prod` back, one `rollback` call at a time, until the live release is `healthy`. A rollback returns to the release that the live one replaced, which `status` shows as `previous_release_id`. Some services need more than one rollback.
- Never roll back to a release created before 2026-09-10T00:00:00Z. If the next rollback would do that, or there is no release to return to, stop and leave that service where it is.
- Each `rollback` call creates a new release and moves one step back, so do not repeat one that already took effect.

Only `prod` is in scope. Do not deploy anything and do not touch `staging`.

Write `/app/rollback-report.json` as `{"rolled_back": {"<service>": "<commit now live in prod>", ...}, "needs_attention": [...]}`. `rolled_back` has an entry for every service you rolled back at least once. `needs_attention` lists, in alphabetical order, the services still not healthy in `prod` when you stopped.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
