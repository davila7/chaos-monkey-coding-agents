The `spokehouse` bike share back office in /app keeps its state in /app/var/state.json, which scheduled jobs read and write. Audits in /app/logs/audit found values in the state that disagree with the upstream books. Every revision of the state is kept in /app/var/snapshots, the scheduler, deploy and operator logs are in /app/logs, the feed files each run read are in /app/feeds, and /app/docs describes the system; /app/docs/triage.md explains how wrong values are traced and lists the cause classes.

Find every defect in the code shipped in /app/spokehouse that makes a run write a wrong state, and write /app/state-report.json with one entry per defect:

    {"causes": [{"class": "<class>", "file": "<path>", "line": <number>, "snapshots": ["<snapshot file name>", ...]}, ...]}

- `class`: one of the classes in /app/docs/triage.md section 3.
- `file` and `line`: the module, as a path relative to /app (for example `spokehouse/feeds.py`), and the number of a line that is wrong, counted in the file as you received it, before your changes.
- `snapshots`: the file name of every snapshot in /app/var/snapshots that this defect made wrong, for example `004412-20270328T111508Z-trips.json`. A snapshot counts for a defect when fixing that defect alone in the shipped code would change the data (everything but `meta`) that its run writes, with the run given the same feed and start time and retried by the scheduler as /app/docs/operations.md section 2 describes. A snapshot can count for more than one defect.

Snapshots written by an earlier release or by operators, and runs that wrote no snapshot, get no entry and are not listed under any defect.

Then fix the code under /app/spokehouse so that the jobs and the store follow the docs. Do not change anything under /app/tests, /app/tools, /app/docs, /app/logs, /app/var or /app/feeds. The package will also be run on other states, feeds and schedules.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
