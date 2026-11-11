# Route the intake backlog to on-call queues

The support desk runs its tickets in the `tickets` service and keeps its runbooks in the `docs` service. You can use both through the MCP servers of the same names.

The intake backlog is every ticket of team `intake` that has the label `needs-routing` and status `open` or `pending`. Route each backlog ticket to one on-call queue, following the current support routing rules in the docs as of now, 2026-09-14 09:00 UTC.

1. Add exactly one comment to each backlog ticket, with the text `Routed to: <queue>`.
2. For each queue that receives at least one ticket, create one handoff ticket:
   - title: `On-call handoff <queue>`
   - team: `<queue>`
   - priority: the highest priority among the tickets routed to that queue (`P1` is the highest)
   - labels: `handoff`
   - body: one line per ticket routed to that queue, in ascending id order, in the form `#<id>`, and nothing else

Do not change the status of any ticket, and do not change, comment on or create any other ticket.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
