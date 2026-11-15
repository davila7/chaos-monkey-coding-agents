# Make the Penwick client safe to retry

The repository in `/app` holds `books`, our integration with Penwick, the ledger service that moves money between our customers' accounts. `/app/books/penwick.py` sends each request once: a lost response or a short outage fails the call, and a caller that repeats a failed call can move money twice. Penwick's API reference is mirrored in the `docs` service, together with our own engineering standards; you can use it through the `docs` MCP server.

Add idempotency keys and retries to the client as Penwick's pages and our current standard for Penwick clients describe: which requests carry an `Idempotency-Key` and how each key is formed, what Penwick answers to a repeated or concurrent request, which failures are tried again, how many times and after which wait, and how an operation that cannot carry a key is kept from being applied twice. The docs service also holds a superseded version of our standard and a draft of a later Penwick version; follow the pages in force.

Callers of `books` must notice nothing but fewer failures. Keep `get_transfer`, `create_transfer`, `reverse_transfer`, `refund_transfer`, `place_hold` and `capture_hold` with their signatures and docstring contracts, keep `Transfer`, `Refund`, `Hold`, `Response`, `Transport` and `ApiError` as they are, and wait only through the transport's `sleep`. Use the Python standard library only. `/app/tests` has a test you can run with `cd /app && python -m unittest`. The client will also be checked against a server that behaves as Penwick's pages describe, on references and accounts you have not seen, with lost responses, outages, rate limits and repeated calls along the way: each call must send exactly the requests and waits that the docs call for, with the right keys and bodies, and return or raise what its docstring promises.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
