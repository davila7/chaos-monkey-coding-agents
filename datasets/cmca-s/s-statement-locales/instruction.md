# Fix the Meridale merchant statements

The repository in `/app` holds `statements`, which builds the monthly statements we send to our merchants from Meridale's settlements report. Meridale is the processor that settles their card sales. Its API reference and the rules its merchant dashboard follows are mirrored in the `docs` service, which you can use through the `docs` MCP server.

Our statements must show the same figures and the same text as the Meridale dashboard, and today they do not. Support has collected these reports:

- Merchants whose account stores a legacy zone name or a fixed UTC offset get no statement at all: the API answers 400.
- The last day of the month is missing from every statement.
- Some daily amounts and many totals differ from the dashboard by one minor unit, and yen and dinar amounts have the wrong number of decimals.
- Amounts are written the US way for every merchant, whatever their locale.
- Meridale's reference marks parameters our client sends as deprecated.

Fix `monthly_statement` in `/app/statements/meridale.py` so that it follows the pages in force; the docs service also holds a superseded page and a draft. Keep its signature and docstring contract, and keep `Merchant`, `Line`, `Statement`, `Response`, `Transport` and `ApiError` as they are, with the values our account records hold today. Use the Python standard library only. `/app/tests` has a test you can run with `cd /app && python -m unittest`. The code will also be checked against a server that behaves as the Meridale reference describes, for merchants you have not seen, in other zones, locales and currencies: each statement must send exactly the one request the reference calls for, with exactly the parameters it requires, and return the lines, amounts and text the dashboard shows.

When you are done, write /app/STATUS.json containing a JSON object with two fields:
"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;
"summary": one or two sentences describing what you did and anything left unfinished.
