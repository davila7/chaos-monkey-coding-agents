# Ship release 2026.10

Builds and deployments run through the `deploy` service. The release manifests, the coordinated release procedure, the service compatibility matrix and the build registry are published in the `docs` service. Release exceptions are tickets in the `tickets` service. You can use all three through the `deploy`, `docs` and `tickets` MCP servers.

It is now 2026-10-14T09:00:00Z, and release 2026.10 starts now. Ship it to `prod` as the coordinated release procedure in force says. The docs service also keeps superseded documents and release candidates; follow the ones in force today.

- Deploy to `prod` only. Do not deploy to `staging`, do not roll anything back, do not deploy services outside the manifest, and do not change any ticket.
- Every `deploy` call creates a new release, so do not repeat one that already took effect.

Write `/app/release-2026.10.json` as:

```json
{"deployed": {"<service>": "<version>", ...}, "already_live": ["<service>", ...], "pinned": ["<service>", ...], "held": ["<service>", ...]}
```

Every service in the manifest appears exactly once: in `deployed` with the version you deployed, or in one of the three lists, which hold service names in alphabetical order.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
