# Ship the 2026-09-14 release plan

Builds and deployments run through the `deploy` service, which you can use through the `deploy` MCP server.

The release plan is `/app/release/plan.csv`: one row per service with the commit to ship and a `hold` flag. Work through every row whose `hold` is `no`; leave held services alone.

1. Build the commit. If the build fails, do not deploy it; the service is `failed_build`.
2. Deploy the build to `staging`, unless that build is already the live release in `staging`.
3. Check the health of the live `staging` release. If it is not `healthy`, the service is `degraded`: do not promote it, and if you deployed it to staging in step 2, roll `staging` back once so it returns to the release it replaced. If someone else had already deployed it, leave staging as it is.
4. If it is healthy, deploy the same build to `prod`, unless it is already the live release in `prod`. The service is `promoted`.

Every `deploy` and every `rollback` call creates a new release, so do not repeat one that already took effect.

Write `/app/release-report.json` as `{"promoted": [...], "failed_build": [...], "degraded": [...]}`, each list holding service names in alphabetical order.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
