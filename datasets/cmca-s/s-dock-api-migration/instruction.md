# Move the Quayline client to API v4

The repository in `/app` holds `yard`, our integration with Quayline, the service that books dock appointments at our warehouses. `/app/yard/quayline.py` still talks to version 3 of Quayline's API, which Quayline has retired. Quayline's API reference and its guide for migrating from v3 to v4 are mirrored in the `docs` service, which you can use through the `docs` MCP server.

Migrate the client to v4 as the migration guide and the v4 reference describe: paths, request and response fields, status values, timestamps and dates, endpoints that moved or were deprecated, and errors. The docs service also holds the retired v3 reference and a draft of a later version; follow the pages in force. A migrated client must not call any endpoint the guide marks as deprecated.

Callers of `yard` must not notice the migration. Keep `get_booking`, `create_booking`, `cancel_booking` and `find_bookings` with their signatures and docstring contracts, and keep `Booking`, `NewBooking`, `Status`, `Response`, `Transport` and `ApiError` as they are, with the values our code uses today. Use the Python standard library only. `/app/tests` has a test you can run with `cd /app && python -m unittest`. The client will also be checked against a server that behaves as the v4 reference describes, on bookings you have not seen: each function must send only the requests the v4 contract calls for, with exactly the fields and parameters it requires, and return what our code got from v3 for the same booking.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
