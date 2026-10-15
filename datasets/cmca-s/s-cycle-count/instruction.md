# Apply the east warehouse cycle count

Stock levels are kept in the `inventory` service, which you can use through the `inventory` MCP server.

The east warehouse was counted on 2026-09-13. The count sheet is `/app/counts/east-2026-09-13.csv`, with one row per counted shelf: the item's sku, the quantity counted, and when that shelf was counted (UTC). Bring the system in line with the count:

- Some shelves were counted twice. For those, the row with the later `counted_at` is the one that holds.
- Stock kept moving after the count. The correct east quantity of an item now is its counted quantity plus every east adjustment of that item recorded after its `counted_at`, leaving out adjustments with reason `count`.
- Make the east on-hand quantity of every counted item equal that figure. Record each correction with `adjust_stock` in warehouse `east`, with reason `count` and reference `CC-0913`.
- A colleague started these corrections and stopped partway. Some of the `CC-0913` adjustments already recorded are right and some are not. Record at most one new correction per item, and none for an item whose east quantity is already correct.
- Some rows name a sku that does not exist. Write those skus to `/app/count-exceptions.txt`, one per line, and do not record anything for them.

Do not change the stock of any other item or warehouse.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
