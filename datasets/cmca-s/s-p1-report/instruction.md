# Report open P1 tickets

The support desk runs its tickets in the `tickets` service, which you can use through the `tickets` MCP server.

Write a report of the open tickets with priority `P1`, per team, to `/app/report.json`. A ticket is unanswered when it has no comment from anyone other than the ticket's own customer. Use this format, with one entry for each of the teams `billing`, `data`, `identity`, `mobile` and `platform`, and the ids in ascending order:

    {"teams": {"billing": {"open_p1": <number of open P1 tickets>, "unanswered": [<ids of unanswered open P1 tickets>]}, ...}}

Only tickets with status `open` count. This is a read-only task: do not change, comment on or create any ticket.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
