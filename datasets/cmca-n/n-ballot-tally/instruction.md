The city counts its ranked-choice contests from the cast vote records that the ballot scanners of every precinct export, in /app/data. Write a Python script at /app/bin/tally.py that tallies every contest of /app/data/election.json round by round by the rules in /app/docs (start with /app/docs/overview.md) and writes the tally file described in /app/docs/output.md. It is run as `python3 /app/bin/tally.py INPUT_DIR OUTPUT_FILE`. Run it on /app/data and save the result as /app/out/tally.json.

From /app, `python -m unittest discover -s tests -t .` runs the script on a few small elections, and `python tools/check_tally.py` compares /app/out/tally.json with the certified results of the current election. The script will also be run on other elections, with other contests, batches and ballots, so it must follow the documented rules rather than what the current files happen to contain. Use only the Python standard library. Do not change anything under /app/data, /app/docs, /app/tests or /app/tools.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
