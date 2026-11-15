The research team fielded a residents survey online, and the form changed twice during fieldwork. The response exports of all three form versions, the codebook, the weighting targets and the table plan are in /app/data. Write a Python script at /app/bin/crosstabs.py that turns them into the response summary and weighted crosstabs by the rules in /app/docs (start with /app/docs/overview.md) and writes the tables file described in /app/docs/output.md. It is run as `python3 /app/bin/crosstabs.py INPUT_DIR OUTPUT_FILE`. Run it on /app/data and save the result as /app/out/tables.json.

From /app, `python -m unittest discover -s tests -t .` runs the script on a few small surveys, and `python tools/check_tables.py` compares /app/out/tables.json with the approved tables of the current survey. The script will also be run on other surveys, with other codebooks, targets, table plans and exports, so it must follow the documented rules rather than what the current files happen to contain. Use only the Python standard library. Do not change anything under /app/data, /app/docs, /app/tests or /app/tools.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
