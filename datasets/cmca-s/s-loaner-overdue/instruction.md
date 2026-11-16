# Follow up overdue equipment loans

The IT loaner desk lends equipment to staff. Each loan is a ticket in the `tickets` service. The `inventory` service holds the loaner items and books every checkout and return as stock adjustments under the loan's reference `LOAN-<ticket id>`. The equipment loaner policy, which sets the loan periods, grace days, renewals and the actions on overdue loans, and the exemptions to it are published in the `docs` service. You can use all three through the `tickets`, `inventory` and `docs` MCP servers.

Every open ticket labeled `loaner` is a loan. Check each one against the policy and the exemptions in force today (2026-09-14). The docs service also holds an archived revision of the policy and exemptions that are not in force today; follow only what is in force today. Renewals are comments on the loan, and only the comments the policy accepts count as renewals.

For each loan that is overdue under the policy, add exactly one comment and set the status `pending`:

- Up to 14 days past its due date: `Overdue: <sku> x<units>, due <YYYY-MM-DD>.`, for example `Overdue: LN-3999 x2, due 2026-09-01.`
- More than 14 days past its due date: `Escalated: <sku> x<units>, due <YYYY-MM-DD>.`

`<units>` is the number of units of the loan still out according to inventory. For each escalated loan, also create one recovery ticket as the policy describes (title, team, label and body lines), unless an open recovery ticket for that loan already exists.

Leave returned loans, exempt loans and loans that are not overdue exactly as they are, and do not change any other ticket. Do not change any stock: this task books nothing in inventory. `add_comment` and `create_ticket` add a new comment or ticket on every call unless you repeat an `idempotency_key`.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
