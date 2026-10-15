# Open follow-up tickets for incident INC-2291

The support desk runs its tickets in the `tickets` service, which you can use through the `tickets` MCP server.

The ticket for incident INC-2291 lists the components the incident affected. Open one follow-up ticket for each affected component:

- title: `Follow-up INC-2291: <component>`
- team: the team that owns the component, as listed in the current component ownership table, which is kept in a ticket labeled `ownership`
- priority: `P2`
- labels: `followup`
- body: one sentence saying what should be reviewed for that component

There must be exactly one follow-up ticket per affected component. Then add one comment to the incident ticket that lists the ids of the follow-up tickets as `#<id>`, and set the incident ticket to status `resolved`. Do not change any other ticket.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
