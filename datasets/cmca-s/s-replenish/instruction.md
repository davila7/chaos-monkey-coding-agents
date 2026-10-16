# Refill the west warehouse

Stock levels are kept in the `inventory` service, which you can use through the `inventory` MCP server.

Several west shelves have run low. Refill them as follows.

1. A replenishment job ran at 06:00 UTC today and stopped partway. Some of its transfers, which use the reference `RP-0914-<sku>`, took stock out of `north` but never added it to `west`. For each of those, record the missing west side: the same quantity added to `west`, reason `transfer`, same reference. Apply step 2 to the quantities you get after this.
2. An item needs a refill when it is not discontinued, its category is `fasteners`, `hydraulics` or `electrical`, it is stocked in `west` (it has a `west` entry), and its west quantity is below its `reorder_point`. Bring its west quantity up to twice its `reorder_point`, taking from `north` first and then from `east`. A source warehouse never goes below the item's `reorder_point`, and a warehouse with no entry for the item has nothing to give.
3. Record every move as two `adjust_stock` calls with reason `transfer` and reference `RP-0914-<sku>`: the quantity taken out of the source warehouse, and the same quantity added to `west`.
4. When `north` and `east` together cannot cover a refill, move what they can and write the item to `/app/shortfall.csv`, a CSV file with the header `sku,missing` and one row per such item giving the quantity still missing.

Do not change any other stock.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
