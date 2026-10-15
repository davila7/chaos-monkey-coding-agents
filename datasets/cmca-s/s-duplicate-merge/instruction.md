# Merge duplicate billing tickets

The support desk runs its tickets in the `tickets` service, which you can use through the `tickets` MCP server.

Some open tickets of the billing team are duplicates. Two open billing tickets are duplicates when they have the same customer and name the same order: the order number is on the line that starts with `Order:` in the ticket body.

For every group of duplicates:

1. Keep the ticket with the lowest id open and unchanged.
2. Set every other ticket of the group to status `duplicate`.
3. Add exactly one comment to each ticket you set to `duplicate`, with the text `Duplicate of #<id>`, where `<id>` is the id of the ticket that stays open.

Only open tickets of the billing team count. Do not change, comment on or create any other ticket.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
