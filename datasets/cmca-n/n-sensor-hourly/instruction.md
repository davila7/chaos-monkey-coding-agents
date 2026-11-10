The weather and air stations of a regional network upload their logger dumps to /app/data. Write a Python script at /app/bin/hourly.py that turns the dumps into the hourly station product by the rules in /app/docs (start with /app/docs/overview.md) and writes the hourly file described in /app/docs/output.md. It is run as `python3 /app/bin/hourly.py INPUT_DIR OUTPUT_FILE`. Run it on /app/data and save the result as /app/out/hourly.json.

From /app, `python -m unittest discover -s tests -t .` runs the script on a few small inputs, and `python tools/check_hourly.py` compares /app/out/hourly.json with the approved hourly values for the current dumps. The script will also be run on dumps from other stations and other periods, so it must follow the documented rules rather than what the current files happen to contain. Use only the Python standard library. Do not change anything under /app/data, /app/docs, /app/tests or /app/tools.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
