Eight depots export their shipments to /app/data as weekly files, each depot in its own format. Write a Python script at /app/bin/summarize.py that builds the shipment summary described in /app/docs/summary-format.md, run it on /app/data, and save its output as /app/out/summary.json. The script will also be run on other exports from the same depots, so it must follow the documented rules rather than what the current files happen to contain.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
