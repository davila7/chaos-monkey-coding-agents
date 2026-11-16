# Finish the Hollin upload client

The repository in `/app` holds `archive`, our integration with Hollin, the file storage service that keeps the documents our customers scan and send us. `/app/archive/hollin.py` was written against an old version of Hollin's upload API, and every upload now fails. Hollin's API reference is mirrored in the `docs` service, together with our own engineering standards; you can use it through the `docs` MCP server.

Rewrite `upload_file` so that it uploads files as Hollin's pages in force and our current upload client standard describe: which chunk size a session uses for each plan (the plan comes as our account records hold it), how the file is cut into parts and how the parts are numbered, the checksum of each part and of the whole file, each in the encoding the docs give, when a saved session may be resumed and what a resumed upload sends again, and how the commit call and its errors are handled, including sessions that expire. The docs service also holds a superseded page of an older Hollin version; it is not in force.

Keep `upload_file` and `file_info` with their signatures and docstring contracts, and keep `Session`, `StoredFile`, `Response`, `Transport` and `ApiError` as they are. Use the Python standard library only. `/app/tests` has a test you can run with `cd /app && python -m unittest`. The client will also be checked against a server that behaves as Hollin's pages describe, with files, plans and saved sessions you have not seen, and with parts lost and sessions dropped along the way: each call must send exactly the requests the docs call for, in order, with the right paths, headers and bodies, call `record` as the docstring says, and return or raise what the docstring promises.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
