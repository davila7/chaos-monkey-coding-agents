# Process the warranty returns

Customers ask for warranty replacements through tickets in the `tickets` service. Products and stock are kept in the `inventory` service. You can use both through the `tickets` and `inventory` MCP servers.

Every open ticket labeled `warranty` is a claim. The warranty policy is the open ticket labeled `warranty-policy`: it decides which claims are covered, what to ship and from which warehouse. A replacement is shipped with one `adjust_stock` call: the replacement sku, the warehouse, delta minus the claim's units, reason `shipment`, reference `RMA-<ticket id>`.

Colleagues shipped some replacements before you without answering the tickets. A claim whose reference already has a `shipment` adjustment has been shipped: ship nothing more, and answer it with that adjustment.

Two open claims for the same serial are one claim. The one with the higher ticket id is a duplicate of the other: answer it as a duplicate and do nothing else for it. This rule comes before every other.

Process the claims one at a time in ticket id order, lowest id first, so that each one sees the stock the ones before it left. Add exactly one comment to each claim and set its status:

- Shipped, by you or before you: `Replacement <sku> shipped from <warehouse> as <adjustment id>.` with the sku and warehouse of the shipment and its adjustment id (for example `adj-123`). Status `resolved`.
- Not covered: `Not covered: <reason>.` with the reason the policy gives. Status `closed`.
- Covered, but no warehouse can ship it: `Backordered: <sku>.` Status `pending`.
- Duplicate: `Duplicate of #<ticket id of the other claim>.` Status `duplicate`.

Ship nothing for a claim that is not covered, backordered or a duplicate. Leave every other ticket and all other stock as they are. Each `adjust_stock` call records a new adjustment, even when repeated with the same arguments.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
