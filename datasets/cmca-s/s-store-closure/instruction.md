# Close the Alameda store

The Alameda store closes today (2026-09-14). Its stock is the `alameda` warehouse of the `inventory` service, which also holds the item records and the stock of the other stores. Its customer tickets are in the `tickets` service, team `store-alameda`. The closure plan (where each item goes, the items that cannot travel, the receiving capacity of each store), the hazardous goods permits and the customer responses for the closure are published in the `docs` service. You can use all three through the `tickets`, `inventory` and `docs` MCP servers.

Carry out the closure exactly as the current closure plan says, under the permits in force today. The docs service also holds superseded revisions; follow only the current ones.

- Stock: empty `alameda` by moving or writing off every unit as the plan says, with `adjust_stock` under the plan's reference. Book nothing else and leave all other stock as it is. Each `adjust_stock` call records a new adjustment, even when repeated with the same arguments.
- Customer tickets: add exactly one comment to each ticket the plan covers, with the matching customer response as written in the docs (the store name filled in where the response has one), and set its status as the plan says. Leave every other ticket unchanged.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
