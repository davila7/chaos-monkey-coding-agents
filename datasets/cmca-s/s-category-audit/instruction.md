# Fix misfiled support tickets

The support desk runs its tickets in the `tickets` service and keeps its procedures in the `docs` service. You can use both through the MCP servers of the same names.

Some tickets of team `support` are filed under the wrong category. Audit every ticket of team `support` with status `open` or `pending` against the current ticket taxonomy in the docs and the documents it points to, as of now, 2026-09-14 09:00 UTC. The docs service also keeps older revisions; use only the ones in force.

The tickets service does not let you edit labels. The desk records a category change as a comment, and a nightly sync applies it to the label.

1. Add exactly one comment to each misfiled ticket, with the text `Category: <category>`, where `<category>` is the ticket's correct category as the taxonomy names it (never an alias).
2. Create one report ticket:
   - title: `Category audit 2026-09-14`
   - team: `support-ops`
   - priority: `P3`
   - labels: `audit`
   - body: one line per ticket you commented on, in ascending id order, in the form `#<id> <filed> -> <category>`, where `<filed>` is the name after `category/` on the ticket's label exactly as written, or `none` when the ticket has no category label, and nothing else

Do not change the status of any ticket, and do not change, comment on or create any other ticket.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
