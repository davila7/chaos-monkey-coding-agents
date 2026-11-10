# Quarantine the lots under recall RC-2611

Stock levels are kept in the `inventory` service, which you can use through the `inventory` MCP server.

A supplier has recalled lots of two of its parts under recall RC-2611. Its notice of 2026-09-10 and the amendment of 2026-09-12 are in `/app/recall/`, together with `part-map.csv`, which maps the supplier's part numbers to our item codes.

How stock is kept:

- Each lot is its own item. Its sku is the item code followed by the lot (for example `HP-4471-L26213-2` is lot 26213-2 of item code HP-4471), and its name gives the lot.
- Stock is held per storage location. The service calls locations warehouses: pass a location name wherever a tool takes `warehouse`. Locations are named `<site>-<bin>`, at three sites, `east`, `west` and `north`, and each site has a quarantine location `<site>-Q`.

What to do:

1. A lot is affected when the notice, as amended, covers it. Where the amendment and the notice differ, the amendment holds.
2. Quarantine every unit of an affected lot that is on hand outside a quarantine location: move it to the quarantine location of the same site. Record each move as two `adjust_stock` calls with reason `transfer` and reference `RC-2611`: the quantity taken out of the location it is in, and the same quantity added to `<site>-Q`.
3. A colleague started on 2026-09-11, working from the notice before the amendment came, and stopped partway. Their moves also use the reference `RC-2611`. Leave the moves that are right as they are. Where a move took units out of a location and never added them to the quarantine location, add them there. Where a move quarantined a lot that is not affected, move those units back to the location they came from, recorded the same way (out of `<site>-Q`, into that location).
4. Write `/app/RC-2611.csv`, a CSV file with the header `sku,quarantined,shipped` and one row per affected lot in the inventory, including lots with nothing left on hand. `quarantined` is the number of units of the lot in quarantine locations when you are done. `shipped` is the number of units of the lot shipped to customers: minus the sum of the lot's adjustments with reason `shipment`.

Do not change any other stock.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
