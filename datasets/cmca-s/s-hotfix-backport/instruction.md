# Roll out hotfix HF-2291

Builds and deployments run through the `deploy` service, which you can use through the `deploy` MCP server.

The advisory is `/app/hotfix/HF-2291.md`, and the changelog of each release branch is in `/app/hotfix/changelog/`. Every live commit is on exactly one release branch, and environments of the same service can run different branches.

The production environments are `prod` and `prod-eu`; `staging` is out of scope. For every production environment of every service the `deploy` service lists, classify its live release and act on it:

1. `not_affected`: the service is not in the advisory's list of affected services, or the live commit is on a branch the advisory does not list as affected. Leave it alone.
2. `already_fixed`: the live commit has the fix. A commit has the fix when, in its branch's changelog, the newest `HF-2291` entry at or below it (the commit itself or an older one) applies the fix rather than reverting it. Leave it alone.
3. Otherwise build the advisory's commit for the live commit's branch, for that service. If the build fails, the environment is `build_failed`: do not deploy anything else in its place. If it succeeds, deploy it to that environment; it is `deployed`.

Do not move an environment to another branch, do not roll anything back, and do not touch `staging`. Every `deploy` call creates a new release, so do not repeat one that already took effect.

Write `/app/hotfix-report.json` as:

```json
{"deployed": {"<service>@<environment>": "<commit now live>", ...}, "already_fixed": [...], "not_affected": [...], "build_failed": [...]}
```

Every production environment appears exactly once, as `<service>@<environment>`; the three lists are in alphabetical order.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
