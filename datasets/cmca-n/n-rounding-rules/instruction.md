The `meterbill` package in /app rounds money in many places, each module in its own way. Move every rounding rule into one new module, `meterbill/money.py`, as described in /app/docs/rounding.md, and follow every rule in that guide: the exact public names and behavior of `money.py`, no rounding of any kind outside it (formatting a number with a fixed number of places counts), no use of the decimal context anywhere, the public functions of the other modules kept, and the command line output unchanged. The commands and the account file format are in /app/docs/cli.md; sample account files are in /app/samples/accounts. The tests in /app/tests must keep passing unchanged; from /app they run with:

    python -m unittest discover -s tests -t .

This is a pure refactor: no figure may change, even where today's behavior looks inconsistent. The result will be checked against the original package with tariff books, account files and quotes other than the ones in /app, through every command and output format, and `meterbill.money` will be called directly on values of its own, so every rule must hold for any input, not only for the samples.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
