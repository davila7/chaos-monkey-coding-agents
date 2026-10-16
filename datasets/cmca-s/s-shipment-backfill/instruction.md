# Record yesterday's shipments

Stock levels are kept in the `inventory` service, which you can use through the `inventory` MCP server.

The warehouse system exported the orders shipped on 2026-09-13 to `/app/shipments/2026-09-13.jsonl`, one order per line: the order id, the warehouse it shipped from, and its lines (sku and quantity). Staff recorded some of these shipments by hand during the day, not always correctly. Make the stock records match the export:

- A shipped line is recorded by `adjust_stock` adjustments with reason `shipment`, the order id as reference, and the order's warehouse. For every line, the adjustments for that order, sku and warehouse must add up to minus the shipped quantity.
- Where nothing was recorded for a line, record it. Where a line was recorded with the wrong quantity, record one more adjustment with the difference, so the total comes out right. Where it was recorded correctly, record nothing.
- The export repeats one order. An order that appears twice shipped once.
- Some lines cannot be recorded because the warehouse does not have the stock. Do not record those lines at all, and write them to `/app/blocked.csv`, a CSV file with the header `order,sku,missing` and one row per such line, where `missing` is the quantity that still needed to be recorded.

Do not change any other stock.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
