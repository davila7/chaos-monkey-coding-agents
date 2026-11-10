# Report support SLA breaches

The support desk runs its tickets in the `tickets` service, which you can use through the `tickets` MCP server.

The support SLA policy is kept in the open ticket labeled `sla-policy`. Apply it to every ticket it covers, measured up to now, 2026-09-14 09:00 UTC, and find the tickets that breached their first-response target, their resolution target, or both.

1. Add exactly one comment to each breached ticket, with the text `SLA breach: <metrics>`, where `<metrics>` is `first-response`, `resolution`, or `first-response, resolution`. A ticket that already has a comment starting with `SLA breach:` was reported by an earlier review: do not comment on it again.
2. Create one ticket that reports the review:
   - title: `SLA breach report 2026-09-14`
   - team: `support-ops`
   - priority: `P2`
   - labels: `sla-report`
   - body: one line per breached ticket, including those reported by an earlier review, in ascending id order, in the form `#<id> <metrics>`, and nothing else

Do not change the status or priority of any ticket, and do not change, comment on or create any other ticket.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
