# Settle the refund requests

Customers ask for refunds through tickets in the `tickets` service. Returned goods arrive at the returns dock, which is the `returns` warehouse in the `inventory` service. The refund policy, the returns dock procedure and the notices that change them are published in the `docs` service. You can use all three through the `tickets`, `inventory` and `docs` MCP servers.

Every open ticket labeled `refund` is a request. Decide and settle each one under the refund policy and the returns dock procedure in force today (2026-09-14). The docs service also holds an archived policy and notices that have ended; follow only what is in force today.

An approved request is refunded only once all of its units have arrived at the dock. The dock books each parcel as a `receipt` adjustment in the `returns` warehouse with reference `RTN-<ticket id>`, and the units of one request can arrive in several parcels. Record every stock movement for a request with that same reference. Colleagues cleared some returned units out of the dock before you without answering the tickets; units already moved out of `returns` under a request's reference are not moved again.

Process the requests one at a time in ticket id order, lowest id first, so that each one sees the stock the ones before it left. Add exactly one comment to each request and set its status:

- Refunded: `Refund <amount> approved for <units> units.` with the refund amount to two decimals, for example `Refund 42.50 approved for 1 units.` Status `resolved`.
- Not refundable: `Not refundable: <reason>.` with the reason the policy gives. Status `closed`.
- Approved, but not every unit has arrived: `Awaiting return: <received> of <units> units received.` Status `pending`.

Move no stock for a request that is not refunded. Leave every other ticket and all other stock as they are. Each `adjust_stock` call records a new adjustment, even when repeated with the same arguments.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
