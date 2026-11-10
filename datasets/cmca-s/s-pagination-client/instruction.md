# Update the Tidewater list client

The repository in `/app` holds `freight`, our integration with Tidewater, our freight carrier. `list_all` in `/app/freight/tidewater.py` still follows an old revision of Tidewater's API and no longer works against it. Tidewater's API reference is mirrored in the `docs` service, which you can use through the `docs` MCP server.

Update `list_all` to the contract in force for Tidewater's list endpoints: paths, pagination, page size, filters, the end of a listing, rate limits and errors. The docs service also holds a superseded revision and a draft; follow the pages in force.

Keep the function's signature and docstring contract, `Response`, `Transport` and `ApiError`, and use the Python standard library only. Every wait must go through the `sleep` argument and every reading of the clock through `now`. `/app/tests` has a test you can run with `cd /app && python -m unittest`. The client will also be checked against a server that behaves as Tidewater's reference describes: it must return every item of the listing once and in order, send only the requests the contract calls for, with the parameters it requires, and wait exactly as long as the contract says.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
