# Reconcile the reservations of kit orders

Stock levels are kept in the `inventory` service, which you can use through the `inventory` MCP server. Free stock is in the warehouse `main`, and units held for open sales orders are in the warehouse `reserved`.

The component reservations of several kit and bundle orders no longer match the orders. Reconcile them. Everything you need is in `/app/kits/`:

- `policy.md`: how reservations, releases and picks are posted, how kits explode into components, which revision of a kit applies, how order lines are amended, and which substitutions are allowed. Follow it.
- `open-orders.csv`: the orders to reconcile, one row per amendment of an order line: order id, line, amendment number, the date the order was created, the sku ordered (a kit or a stocked sku), the quantity and the status.
- `kit-bom.csv`: the components of each kit by revision, with the date each revision took effect.

What to do:

1. For every order in `open-orders.csv`, make the reservation the order holds for each sku equal to what the policy says it should hold. Use `adjust_stock` with the order id as reference, as the policy describes. Some reservations are right, and some are not.
2. Write `/app/kit-reservations.csv`, a CSV file with the header `order,sku,required,picked,reserved` and one row for each order in `open-orders.csv` and each sku that the order requires or that has a posting in `reserved` under the order, including rows that need no change. All three quantities are in each: `required` is the units of the sku the order requires, `picked` the units picked under the order that count toward the sku, and `reserved` the reservation the order holds for the sku when you are done.

Do not change anything for orders that are not in `open-orders.csv`, and do not change any other stock.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
