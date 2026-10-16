# Process the damage reports

The warehouse team reports damaged goods as tickets in the `tickets` service. Stock levels are kept in the `inventory` service. You can use both through the `tickets` and `inventory` MCP servers.

Every open ticket labeled `damage` names a sku, a warehouse and a number of damaged units. Process each of them:

- Record the damage in inventory with `adjust_stock`: the damaged units taken out of that item in that warehouse, reason `damage`, reference `TCK-<ticket id>`. Then add one comment to the ticket that contains the id of that adjustment (for example `adj-123`), and set the ticket to `resolved`.
- Some reports were already recorded in inventory under their `TCK-<ticket id>` reference by a colleague who did not answer the ticket. Do not record those again: add the comment with the id of the existing adjustment and set the ticket to `resolved`.
- If the warehouse does not hold enough units of the item to take the damage out, record nothing, add one comment to the ticket that says `insufficient stock`, and set it to `pending`.

Add exactly one comment to each ticket you process. Leave every other ticket and all other stock as they are. Each `adjust_stock` call records a new adjustment, even when repeated with the same arguments.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
