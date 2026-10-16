# Process the damage reports

The warehouse team reports damaged goods as tickets in the `tickets` service. Stock levels are kept in the `inventory` service. You can use both through the `tickets` and `inventory` MCP servers.

Every open ticket labeled `damage` is a report that names a sku, a warehouse and a number of damaged units. Its damage is recorded in inventory as adjustments with reason `damage` and reference `TCK-<ticket id>`, taken from that item in that warehouse. A report is recorded when the `damage` adjustments under its reference add up to minus its damaged units. Colleagues recorded some reports before you without answering the tickets, not always correctly.

Process the reports one at a time in ticket id order, lowest id first. For each report:

- If it is already recorded, record nothing. Add one comment to the ticket that contains the id of the existing adjustment (for example `adj-123`), and set the ticket to `resolved`.
- Otherwise record the difference with one `adjust_stock` call: the units still missing so that the `damage` adjustments under its reference add up to minus its damaged units, reason `damage`, reference `TCK-<ticket id>`. Then add one comment that contains the id of the adjustment you just recorded, and set the ticket to `resolved`.
- If the warehouse does not hold enough units of the item to take out that difference, given the stock left after the reports before it, record nothing, add one comment that says `insufficient stock`, and set the ticket to `pending`.

Add exactly one comment to each ticket you process. Leave every other ticket and all other stock as they are. Each `adjust_stock` call records a new adjustment, even when repeated with the same arguments.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
