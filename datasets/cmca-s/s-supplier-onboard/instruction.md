# Onboard the new suppliers

Procurement asks for new suppliers through tickets in the `tickets` service. Each supplier first sends trial units of the item it will deliver; the trial units wait in the `inspection` warehouse of the `inventory` service, which also holds the item records. The supplier onboarding policy, the onboarding checks (the approvals a request needs and who may give them) and the exceptions to them are published in the `docs` service. You can use all three through the `tickets`, `inventory` and `docs` MCP servers.

Every open ticket labeled `supplier-onboarding` is a request. Decide each one under the policy, the checks and the exceptions in force today (2026-09-14). The docs service also holds archived revisions and exceptions that are not in force today; follow only what is in force today. Approvals are comments on the request, and only the comments the onboarding checks accept count as approvals.

Process the requests one at a time in ticket id order, lowest id first: a supplier onboarded by one request makes a later request for the same supplier code a duplicate. Add exactly one comment to each request and set its status:

- Duplicate: `Duplicate: <code> already onboarded.` Status `duplicate`.
- Rejected: `Rejected: item not eligible.` or `Rejected: trial failed inspection.` Status `closed`.
- Waiting for approvals: `Waiting for approval: <roles>.` with the missing roles in the order procurement, finance, compliance, for example `Waiting for approval: finance, compliance.` Status `pending`.
- Waiting for the trial: `Waiting for trial delivery: <received> of <units> units received.` Status `pending`.
- Onboarded: `Onboarded: <code>.` Status `resolved`.

Move trial units only as the policy says, under the request's reference `ONB-<ticket id>`. Leave every other ticket and all other stock as they are. Each `adjust_stock` call records a new adjustment, even when repeated with the same arguments.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
