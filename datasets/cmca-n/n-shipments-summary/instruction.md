Three warehouses export their shipments to /app/data in different formats. Produce /app/out/summary.json as described in /app/docs/summary-format.md. You may write and run any scripts you need.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
