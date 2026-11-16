# Correct support contract entitlements

The support desk runs its tickets in the `tickets` service and keeps its procedures in the `docs` service. You can use both through the MCP servers of the same names.

Every support ticket should carry the priority, response target and tags that its account's support contract entitles it to. Some do not: contracts have been upgraded, downgraded or have lapsed, and some accounts are covered through a parent account. Check every ticket of team `support` with status `open` or `pending` against the current support contract entitlements in the docs and the documents they point to, as of now, 2026-09-14 09:00 UTC. The docs service also keeps older revisions; use only the ones in force.

The tickets service does not let you edit priorities or labels. The desk records an entitlement correction as a comment, and a nightly sync applies it to the ticket.

1. Add exactly one comment to each ticket that needs a correction, with the text `Entitlement: <priority> <labels>`, where `<priority>` is the ticket's entitled priority and `<labels>` is the complete set of entitlement labels the ticket should carry, in alphabetical order, separated by single spaces.
2. Create one report ticket:
   - title: `Contract tier corrections 2026-09-14`
   - team: `support-ops`
   - priority: `P3`
   - labels: `entitlements`
   - body: one line per ticket you commented on, in ascending id order, in the form `#<id> <account> <tier>`, where `<account>` is the account id exactly as the ticket's `Account:` line writes it, or `none` when the ticket has no such line, and `<tier>` is the tier the account has now, and nothing else

Do not change the status of any ticket, and do not change, comment on or create any other ticket.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
