The public library bills overdue fees once a month from the circulation exports of its branches, in /app/data. Write a Python script at /app/bin/fees.py that turns the exports and the lending files into the fee statements by the rules in /app/docs (start with /app/docs/overview.md) and writes the statements file described in /app/docs/output.md. It is run as `python3 /app/bin/fees.py INPUT_DIR OUTPUT_FILE`. Run it on /app/data and save the result as /app/out/statements.json.

From /app, `python -m unittest discover -s tests -t .` runs the script on a few small inputs, and `python tools/check_fees.py` compares /app/out/statements.json with the approved statements for the current period. The script will also be run on the exports and lending files of other periods, with other branches, patrons and calendars, so it must follow the documented rules rather than what the current files happen to contain. Use only the Python standard library. Do not change anything under /app/data, /app/docs, /app/tests or /app/tools.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
