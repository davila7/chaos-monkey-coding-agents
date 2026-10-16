A user reports that the monthly totals of the `tally` program changed when they upgraded from release 2.3.0 to 2.4.0. Their report and the ledger file they used are in /app/reports/issue-412/. The program's git repository, with its history and release tags, is /app/repo; /app/repo/docs describes the program, its ledger format and how to run it.

Find the commit that introduced the regression described in the report. A commit counts as bad only if it gives the totals the report shows for 2.4.0, and as good only if it gives the totals the report shows for 2.3.0; commits between the two releases that fail to run or give other totals have other problems and are neither good nor bad for this question. Then find the file whose change in that commit causes the regression, and the earliest tag in the repository that contains the commit. Write the answer to /app/answer.json as:

    {"commit": "<full 40-character commit id>", "file": "<path relative to the repository root>", "first_tag": "<tag name>"}

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
