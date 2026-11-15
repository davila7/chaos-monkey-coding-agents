# Consolidate the reserve bins

Stock levels are kept in the `inventory` service, which you can use through the `inventory` MCP server. Each lot is its own item, and the service calls bins warehouses: pass a bin id wherever a tool takes `warehouse`.

Lots in our reserve zones are spread over many half-empty bins. Consolidate them as consolidation `CONS-0914`. Everything you need is in `/app/consolidation/`:

- `rules.md`: the zones, the count holds, the bin rules (capacity by unit of measure, lots that must not be mixed, categories that may not share a bin) and how each lot's target bin is chosen. Follow it.
- `bins.csv`: every bin with its zone and bin type.
- `bin-types.csv`: the most that one bin of each type holds of each stock unit.
- `count-holds.csv`: the count holds placed on bins.

What to do:

1. Make every move the consolidation calls for, as `rules.md` describes, with `adjust_stock`, reason `transfer` and reference `CONS-0914`. Some lots need no move, and some cannot be moved.
2. Write `/app/move-plan.csv`, a CSV file with the header `sku,from_bin,to_bin,qty` and one row for every move you made: the lot, the bin it was taken out of, the bin it was added to, and the quantity in the item's stock unit. Write no row for a lot that does not move.

Do not change any other stock.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
