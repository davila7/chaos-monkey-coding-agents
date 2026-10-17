"""Renders the files of the tally project from a state dictionary.

Every commit of the generated history is a state; the files of a commit are render(state).
"""
from copy import deepcopy

PKG_DOC = '"""tally: monthly totals from ledger files."""\n'

CURRENCIES_BASE = [("USD", "US dollar", 2), ("EUR", "Euro", 2), ("GBP", "Pound sterling", 2),
                   ("CAD", "Canadian dollar", 2), ("JPY", "Yen", 0), ("CHF", "Swiss franc", 2)]

HELP = {
    ("report", "month"): ["month to total, as YYYY-MM", "the month to report, YYYY-MM",
                          "month in YYYY-MM form", "calendar month to total (YYYY-MM)"],
    ("report", "account"): ["only this account", "limit the report to one account",
                            "report a single account (case does not matter)"],
    ("report", "base"): ["currency of the totals (USD if not given)", "report currency; USD when omitted",
                         "convert every amount to this currency first (USD when omitted)"],
    ("export", "format"): ["output format, see `tally formats`", "one of the names `tally formats` lists",
                           "export format name"],
    ("tally", "description"): ["Monthly totals from ledger files.", "Totals and exports for CSV ledgers.",
                               "Reports and exports for CSV ledger files."],
}

DOCSTRINGS = {
    "canonical": ["Canonical account name: upper case, retired names mapped to their successors.",
                  "Upper-cased account name with aliases resolved.",
                  "The name an account is reported under."],
    "convert": ["Amount in another currency, at the fixed rates of this release.",
                "Converts an amount between two currencies through USD.",
                "Converts amount from currency to base using RATES."],
    "month_of": ["YYYY-MM of a date.", "The month of a date as YYYY-MM.", "Month key of a date."],
    "format_amount": ["Two decimals, half up; with grouping, thousands separated by commas.",
                      "Formats an amount for reports.", "Text of an amount with exactly two decimals."],
    "month_bounds": ["First and last day of a YYYY-MM month.", "Inclusive date range of a month.",
                     "(first, last) dates of the month."],
    "in_month": ["Whether a booking date falls in the month.", "True when d lies in month (inclusive).",
                 "Month membership of a date."],
    "read_ledger": ["Rows of one ledger file.", "Reads a CSV ledger into rows.",
                    "Parses a ledger file; blank rows carry no data."],
    "to_instant": ["Instant of an ISO 8601 date or date-time, in UTC. A date alone is midnight UTC, a date-time "
                   "without offset is taken as UTC.",
                   "UTC instant of an ISO 8601 text; naive values are read as UTC.",
                   "Parses ISO 8601 and returns an aware UTC datetime (naive input is taken as UTC)."],
}


def initial_state():
    return {
        "version": "2.0.0",
        "currencies": list(CURRENCIES_BASE),
        "formats": [],
        "format_tests": [],
        "aliases": [],
        "usage_notes": [],
        "dev_notes": [],
        "changelog": [("2.0.0", ["First release of the 2.x line."])],
        "help": {k: 0 for k in HELP},
        "doc": {k: 0 for k in DOCSTRINGS},
        "readers_bom": False,
        "readers_blank": False,
        "readers_upper_currency": False,
        "readers_memo_strip": False,
        "parse_when": "local",
        "dates": "v1",
        "amount": "v1",
        "rates_path": "tally",
        "report_import": "tally",
        "grouping": False,
        "export_header": "when",
        "month_bounds": "arith",
        "report_rename": False,
        "test_readers_z": False,
        "offsets_note": False,
        "export_seconds": False,
    }


def copy_state(s):
    return deepcopy(s)


def doc(s, key):
    return DOCSTRINGS[key][s["doc"][key] % len(DOCSTRINGS[key])]


def helptext(s, key):
    return HELP[key][s["help"][key] % len(HELP[key])]


def r_init(s):
    return PKG_DOC + f'\n__version__ = "{s["version"]}"\n'


MAIN = '''from tally.cli import main

raise SystemExit(main())
'''


def r_cli(s):
    return '''"""Command line entry point: python -m tally COMMAND ..."""
import argparse
import sys

from tally import __version__
from tally.io.readers import read_ledger


def load(paths):
    rows = []
    for path in paths:
        rows.extend(read_ledger(path))
    return rows


def cmd_report(args):
    from tally.report import monthly_totals, render

    rows = load(args.files)
    if args.account:
        rows = [r for r in rows if r.account == args.account.strip().upper()]
    print(render(monthly_totals(rows, args.month, args.base or "USD"), args.month))
    return 0


def cmd_export(args):
    from tally.formats import REGISTRY

    if args.format not in REGISTRY:
        print(f"tally: unknown format {args.format!r}", file=sys.stderr)
        return 2
    REGISTRY[args.format](load(args.files), sys.stdout)
    return 0


def cmd_currencies(args):
    from tally.data.currencies import CURRENCIES

    for code, name, minor in CURRENCIES:
        print(f"{code}  {minor}  {name}")
    return 0


def cmd_formats(args):
    from tally.formats import REGISTRY

    for name in sorted(REGISTRY):
        print(name)
    return 0


COMMANDS = {"report": cmd_report, "export": cmd_export, "currencies": cmd_currencies, "formats": cmd_formats}


def build_parser():
    p = argparse.ArgumentParser(prog="tally", description="@DESC@")
    p.add_argument("--version", action="version", version=f"tally {__version__}")
    sub = p.add_subparsers(dest="command", required=True)
    r = sub.add_parser("report", help="monthly totals per account")
    r.add_argument("--month", required=True, help="@MONTH@")
    r.add_argument("--account", help="@ACCOUNT@")
    r.add_argument("--base", help="@BASE@")
    r.add_argument("files", nargs="+", help="ledger files")
    e = sub.add_parser("export", help="write the rows of ledgers in another format")
    e.add_argument("--format", required=True, help="@FORMAT@")
    e.add_argument("files", nargs="+", help="ledger files")
    sub.add_parser("currencies", help="list known currencies")
    sub.add_parser("formats", help="list export formats")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    return COMMANDS[args.command](args)
'''.replace("@DESC@", helptext(s, ("tally", "description"))).replace(
        "@MONTH@", helptext(s, ("report", "month"))).replace("@ACCOUNT@", helptext(s, ("report", "account"))).replace(
        "@BASE@", helptext(s, ("report", "base"))).replace("@FORMAT@", helptext(s, ("export", "format")))


def r_readers(s):
    dt_import = "from datetime import date, datetime" if s["parse_when"] in ("dt", "dtz") else "from datetime import date"
    imports = ["import csv", "from dataclasses import dataclass", dt_import,
               "from decimal import Decimal", "", "from tally.accounts import canonical"]
    if s["parse_when"] in ("stamp", "shared"):
        imports.append("from tally.dates import parse_stamp")
    imports.append("from tally.money import parse_amount")
    if s["parse_when"] == "local":
        pw = '''def parse_when(text):
    """Booking date of a row: the date as written, whatever time or offset follows it."""
    return date.fromisoformat(text.strip()[:10])
'''
    elif s["parse_when"] == "dt":
        pw = '''def parse_when(text):
    """Booking date of a row: the local date of the written date or date-time; the offset is not applied."""
    return datetime.fromisoformat(text.strip()).date()
'''
    elif s["parse_when"] == "dtz":
        pw = '''def parse_when(text):
    """Booking date of a row: the local date of the written date or date-time; the offset is not applied."""
    text = text.strip()
    if text.endswith("Z"):
        text = text[:-1]
    return datetime.fromisoformat(text).date()
'''
    elif s["parse_when"] == "stamp":
        pw = '''def parse_when(text):
    """Booking date of a row: the date part of the written date or date-time."""
    return parse_stamp(text).date()
'''
    else:
        pw = '''def parse_when(text):
    """Booking date of a row."""
    stamp = parse_stamp(text)
    return date(stamp.year, stamp.month, stamp.day)
'''
    enc = "utf-8-sig" if s["readers_bom"] else "utf-8"
    blank = ('            if not any((v or "").strip() for v in rec.values()):\n                continue\n'
             if s["readers_blank"] else "")
    cur = '(rec.get("currency") or "USD").strip()'
    if s["readers_upper_currency"]:
        cur += ".upper()"
    memo = '(rec.get("memo") or "").strip()' if s["readers_memo_strip"] else 'rec.get("memo") or ""'
    return f'''"""Reading ledger files (CSV with the columns id, when, account, amount, currency, memo)."""
{chr(10).join(imports)}


@dataclass
class Row:
    id: str
    when: date
    stamp: str
    account: str
    amount: Decimal
    currency: str
    memo: str


{pw}

def read_ledger(path):
    """{doc(s, "read_ledger")}"""
    rows = []
    with open(path, newline="", encoding="{enc}") as fh:
        for rec in csv.DictReader(fh):
{blank}            rows.append(Row(
                id=rec["id"].strip(),
                when=parse_when(rec["when"]),
                stamp=rec["when"].strip(),
                account=canonical(rec["account"]),
                amount=parse_amount(rec["amount"]),
                currency={cur},
                memo={memo},
            ))
    return rows
'''


AMOUNT = {
    "v1": '''    s = text.strip().replace(",", "")
    negative = s.startswith("(") and s.endswith(")")
    if negative:
        s = s[1:-1]
    value = Decimal(s)
    return -value if negative else value
''',
    "bug": '''    s = text.strip().replace(",", "")
    s = s.lstrip("+").strip("$\\u20ac\\u00a3")
    negative = s.startswith("-")
    s = s.strip("()-")
    value = Decimal(s)
    return -value if negative else value
''',
    "fixed": '''    s = text.strip().replace(",", "")
    s = s.lstrip("+").strip("$\\u20ac\\u00a3")
    negative = s.startswith("-") or (s.startswith("(") and s.endswith(")"))
    s = s.strip("()-")
    value = Decimal(s)
    return -value if negative else value
''',
}


def r_money(s):
    return f'''"""Amounts as Decimal values."""
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def parse_amount(text):
    """Amount of a ledger cell: commas group thousands; parentheses or a minus sign mark a negative amount."""
{AMOUNT[s["amount"]]}

def format_amount(value, grouping=False):
    """{doc(s, "format_amount")}"""
    q = Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)
    return f"{{q:,.2f}}" if grouping else f"{{q:.2f}}"
'''


DATES_PARSE = {
    "v1": '''

def to_instant(text):
    """@DOC@"""
    dt = datetime.fromisoformat(text.strip())
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
''',
    "stamp": '''

def parse_stamp(text):
    """Date-time of an ISO 8601 date or date-time as written; a date alone is midnight, an offset is kept."""
    text = text.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)


def to_instant(text):
    """@DOC@"""
    dt = parse_stamp(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
''',
    "utc": '''

def parse_stamp(text):
    """Date-time of an ISO 8601 date or date-time; naive values are read as UTC."""
    dt = datetime.fromisoformat(text.strip())
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def to_instant(text):
    """@DOC@"""
    return parse_stamp(text)
''',
}


def r_dates(s):
    return f'''"""Date and time helpers."""
from datetime import datetime, timezone
{DATES_PARSE[s["dates"]].replace("@DOC@", doc(s, "to_instant"))}

def month_of(d):
    """{doc(s, "month_of")}"""
    return f"{{d.year:04d}}-{{d.month:02d}}"
'''


def r_periods(s):
    if s["month_bounds"] == "arith":
        head = "from datetime import date, timedelta\n"
        body = '''    year, mon = (int(x) for x in month.split("-"))
    first = date(year, mon, 1)
    following = date(year + (mon == 12), mon % 12 + 1, 1)
    return first, following - timedelta(days=1)
'''
    else:
        head = "import calendar\nfrom datetime import date\n"
        body = '''    year, mon = (int(x) for x in month.split("-"))
    return date(year, mon, 1), date(year, mon, calendar.monthrange(year, mon)[1])
'''
    return f'''"""Reporting periods."""
{head}

def month_bounds(month):
    """{doc(s, "month_bounds")}"""
{body}

def in_month(d, month):
    """{doc(s, "in_month")}"""
    first, last = month_bounds(month)
    return first <= d <= last
'''


def r_rates(s):
    return f'''"""Exchange rates to USD, fixed for each release."""
from decimal import Decimal

RATES = {{
    "USD": Decimal("1"),
    "EUR": Decimal("1.0840"),
    "GBP": Decimal("1.2710"),
    "CAD": Decimal("0.7350"),
    "JPY": Decimal("0.006710"),
    "CHF": Decimal("1.1290"),
}}


def convert(amount, currency, base):
    """{doc(s, "convert")}"""
    if currency == base:
        return amount
    return amount * RATES[currency] / RATES[base]
'''


def r_report(s):
    name = "by_account" if s["report_rename"] else "totals"
    mod = "tally.rates" if s["report_import"] == "tally" else "tally.data.rates"
    grp = ", grouping=True" if s["grouping"] else ""
    return f'''"""Monthly totals per account."""
from decimal import Decimal

from {mod} import convert
from tally.money import format_amount
from tally.periods import in_month


def monthly_totals(rows, month, base):
    """Sum of the amounts of each account over the rows booked in month, in currency base."""
    {name} = {{}}
    for row in rows:
        if not in_month(row.when, month):
            continue
        amount = convert(row.amount, row.currency, base)
        {name}[row.account] = {name}.get(row.account, Decimal("0")) + amount
    return {name}


def render(totals, month):
    width = max([len(a) for a in totals] + [5])
    lines = [f"Totals for {{month}}"]
    for account in sorted(totals):
        lines.append(f"{{account:<{{width}}}}  {{format_amount(totals[account]{grp}):>14}}")
    grand = sum(totals.values(), Decimal("0"))
    lines.append(f"{{'TOTAL':<{{width}}}}  {{format_amount(grand{grp}):>14}}")
    return "\\n".join(lines)
'''


def r_accounts(s):
    body = "".join(f'    "{old}": "{new}",\n' for old, new in s["aliases"])
    return f'''"""Account names."""

ALIASES = {{
{body}}}


def canonical(name):
    """{doc(s, "canonical")}"""
    key = name.strip().upper()
    return ALIASES.get(key, key)
'''


def r_currencies(s):
    body = "".join(f'    ("{c}", "{n}", {m}),\n' for c, n, m in s["currencies"])
    return f'"""Known currencies: code, name, minor units."""\n\nCURRENCIES = [\n{body}]\n'


def r_csvfmt(s):
    col = "when" if s["export_header"] == "when" else "date"
    ts = 'timespec="seconds"' if s["export_seconds"] else ""
    return f'''"""CSV export."""
import csv

from tally.dates import to_instant

HEADER = ["id", "{col}", "when_utc", "account", "amount", "currency", "memo"]


def write(rows, fh):
    w = csv.writer(fh, lineterminator="\\n")
    w.writerow(HEADER)
    for r in rows:
        w.writerow([r.id, r.when.isoformat(), to_instant(r.stamp).isoformat({ts}), r.account, str(r.amount),
                    r.currency, r.memo])
'''


JSONFMT = '''"""JSON export: one array of objects."""
import json


def write(rows, fh):
    json.dump([{"id": r.id, "when": r.when.isoformat(), "account": r.account, "amount": str(r.amount),
                "currency": r.currency, "memo": r.memo} for r in rows], fh, indent=1)
    fh.write("\\n")
'''

# name: (kind, parameter, description)
FORMATS = [
    ("tsv", "sep", "\\t", "Tab-separated values"), ("psv", "sep", "|", "Pipe-separated values"),
    ("ssv", "sep", ";", "Semicolon-separated values"),
    ("markdown", "line", "| {id} | {when} | {account} | {amount} | {currency} |", "Markdown table rows"),
    ("ndjson", "json", "", "One JSON object per line"),
    ("html", "line", "<tr><td>{id}</td><td>{when}</td><td>{account}</td><td>{amount}</td></tr>", "HTML table rows"),
    ("xml", "line", "<row id='{id}' when='{when}' account='{account}' amount='{amount}'/>", "XML row elements"),
    ("qif", "line", "D{when}\\nT{amount}\\nP{account}\\n^", "Quicken interchange records"),
    ("fixed", "line", "{id:<12}{when:<12}{account:<16}{amount:>14}", "Fixed-width columns"),
    ("latex", "line", "{id} & {when} & {account} & {amount} \\\\\\\\", "LaTeX tabular rows"),
    ("ledger", "line", "{when} {memo}\\n    {account}  {amount} {currency}", "Plain-text ledger postings"),
    ("sql", "line", "INSERT INTO rows VALUES ('{id}', '{when}', '{account}', {amount});", "SQL insert statements"),
    ("yaml", "line", "- id: {id}\\n  when: {when}\\n  account: {account}\\n  amount: {amount}", "YAML list"),
    ("ascii", "line", "{when}  {account:<16} {amount:>12} {currency}", "Aligned text columns"),
]
FORMAT_INFO = {n: (k, p, d) for n, k, p, d in FORMATS}


def r_format(name):
    kind, param, desc = FORMAT_INFO[name]
    if kind == "sep":
        return f'''"""{desc}."""


def write(rows, fh):
    fh.write("{param}".join(["id", "when", "account", "amount", "currency", "memo"]) + "\\n")
    for r in rows:
        fh.write("{param}".join([r.id, r.when.isoformat(), r.account, str(r.amount), r.currency, r.memo]) + "\\n")
'''
    if kind == "json":
        return f'''"""{desc}."""
import json


def write(rows, fh):
    for r in rows:
        fh.write(json.dumps({{"id": r.id, "when": r.when.isoformat(), "account": r.account,
                             "amount": str(r.amount), "currency": r.currency}}) + "\\n")
'''
    return f'''"""{desc}."""

LINE = "{param}"


def write(rows, fh):
    for r in rows:
        fh.write(LINE.format(id=r.id, when=r.when.isoformat(), account=r.account, amount=str(r.amount),
                             currency=r.currency, memo=r.memo) + "\\n")
'''


def r_formats_init(s):
    mods = ["csvfmt", "jsonfmt"] + [f"fmt_{n}" for n in s["formats"]]
    imports = "".join(f"from tally.formats import {m}\n" for m in mods)
    entries = '    "csv": csvfmt.write,\n    "json": jsonfmt.write,\n' + "".join(
        f'    "{n}": fmt_{n}.write,\n' for n in s["formats"])
    return f'"""Export formats by name."""\n{imports}\nREGISTRY = {{\n{entries}}}\n'


TEST_HEAD = '''import io
import unittest
from datetime import date
from decimal import Decimal

'''


def r_test_money(s):
    return TEST_HEAD + '''from tally.money import format_amount, parse_amount


class AmountTests(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(parse_amount("12.50"), Decimal("12.50"))

    def test_grouped(self):
        self.assertEqual(parse_amount("1,234.50"), Decimal("1234.50"))

    def test_minus(self):
        self.assertEqual(parse_amount("-3.10"), Decimal("-3.10"))

    def test_parentheses(self):
        self.assertEqual(parse_amount("(12.50)"), Decimal("-12.50"))

    def test_format(self):
        self.assertEqual(format_amount(Decimal("1234.5")), "1234.50")
        self.assertEqual(format_amount(Decimal("1234.5"), grouping=True), "1,234.50")
        self.assertEqual(format_amount(Decimal("0.005")), "0.01")


if __name__ == "__main__":
    unittest.main()
'''


def r_test_periods(s):
    return TEST_HEAD + '''from tally.periods import in_month, month_bounds


class PeriodTests(unittest.TestCase):
    def test_bounds(self):
        self.assertEqual(month_bounds("2024-02"), (date(2024, 2, 1), date(2024, 2, 29)))
        self.assertEqual(month_bounds("2025-12"), (date(2025, 12, 1), date(2025, 12, 31)))

    def test_membership(self):
        self.assertTrue(in_month(date(2026, 3, 31), "2026-03"))
        self.assertFalse(in_month(date(2026, 4, 1), "2026-03"))


if __name__ == "__main__":
    unittest.main()
'''


def r_test_readers(s):
    z = '''
    def test_utc_suffix(self):
        self.assertEqual(parse_when("2026-03-31T12:00:00Z"), date(2026, 3, 31))
''' if s["test_readers_z"] else ""
    return TEST_HEAD + f'''from tally.io.readers import parse_when


class WhenTests(unittest.TestCase):
    def test_date(self):
        self.assertEqual(parse_when("2026-03-31"), date(2026, 3, 31))

    def test_date_time(self):
        self.assertEqual(parse_when("2026-03-31T10:00:00"), date(2026, 3, 31))
{z}

if __name__ == "__main__":
    unittest.main()
'''


def r_test_export(s):
    return TEST_HEAD + '''from tally.formats import csvfmt
from tally.io.readers import Row


class ExportTests(unittest.TestCase):
    def test_csv_header(self):
        out = io.StringIO()
        csvfmt.write([Row("a1", date(2026, 1, 2), "2026-01-02T08:00:00-05:00", "OPS", Decimal("5.00"), "USD", "")], out)
        lines = out.getvalue().splitlines()
        self.assertEqual(lines[0], "id,when,when_utc,account,amount,currency,memo")
        self.assertEqual(lines[1], "a1,2026-01-02,2026-01-02T13:00:00+00:00,OPS,5.00,USD,")


if __name__ == "__main__":
    unittest.main()
'''


def r_test_formats(s):
    tests = "".join(f'''
    def test_{n}(self):
        out = io.StringIO()
        REGISTRY["{n}"](ROWS, out)
        self.assertIn("2026-01-02", out.getvalue())
''' for n in s["format_tests"])
    return TEST_HEAD + f'''from tally.formats import REGISTRY
from tally.io.readers import Row

ROWS = [Row("a1", date(2026, 1, 2), "2026-01-02", "OPS", Decimal("5.00"), "USD", "fuel")]


class FormatTests(unittest.TestCase):
    def test_registry(self):
        self.assertIn("csv", REGISTRY)
        self.assertIn("json", REGISTRY)
{tests}

if __name__ == "__main__":
    unittest.main()
'''


def r_usage(s):
    notes = "".join(f"- {n}\n" for n in s["usage_notes"])
    return f'''# Using tally

    python -m tally report --month 2026-03 ledger.csv [more.csv ...]
    python -m tally report --month 2026-03 --account OPS-EAST ledger.csv
    python -m tally export --format csv ledger.csv
    python -m tally formats
    python -m tally currencies

`report` prints one line per account with the sum of the amounts booked in the month, then a
`TOTAL` line. Amounts in other currencies are converted with the fixed rates of the release.

## Notes

{notes}'''


def r_ledger_format(s):
    extra = ("\nAn offset never moves a row to another day: `2026-03-31T23:10:00-05:00` is booked on\n"
             "2026-03-31, and so is `2026-03-31T00:20:00+09:00`.\n") if s["offsets_note"] else ""
    return f'''# Ledger files

A ledger is a CSV file with a header row and the columns `id`, `when`, `account`, `amount`,
`currency` and `memo`.

- `when`: an ISO 8601 date (`2026-03-31`) or date-time, with or without a UTC offset
  (`2026-03-31T18:45:00-05:00`). A row is booked on the date written in this field, the local
  date of whoever wrote the row; the time and the offset do not change the booking date. Export
  formats that need an instant (`when_utc` in CSV exports) convert with the offset.
{extra}- `account`: account name; case does not matter, retired names are mapped to their successors.
- `amount`: decimal point `.`, optional `,` thousands separators; a negative amount has a leading
  `-` or is written in parentheses, `(12.50)`.
- `currency`: ISO 4217 code, USD when empty.
- `memo`: free text.
'''


def r_development(s):
    notes = "".join(f"- {n}\n" for n in s["dev_notes"])
    return f'''# Development

Run the unit tests from the repository root:

    python -m unittest discover -s tests

Run the program from the repository root with `python -m tally`. The package has no
dependencies outside the Python standard library.

## Conventions

{notes}'''


def r_changelog(s):
    out = ["# Changelog", ""]
    for ver, entries in reversed(s["changelog"]):
        out.append(f"## {ver}")
        out.append("")
        out.extend(f"- {e}" for e in entries)
        out.append("")
    return "\n".join(out)


def r_pyproject(s):
    return f'''[project]
name = "tally"
version = "{s["version"]}"
description = "Monthly totals from ledger files"
requires-python = ">=3.10"
'''


def render(s):
    files = {
        ".gitignore": "__pycache__/\n*.pyc\n/build/\n",
        "pyproject.toml": r_pyproject(s),
        "CHANGELOG.md": r_changelog(s),
        "docs/usage.md": r_usage(s),
        "docs/ledger-format.md": r_ledger_format(s),
        "docs/development.md": r_development(s),
        "tally/__init__.py": r_init(s),
        "tally/__main__.py": MAIN,
        "tally/cli.py": r_cli(s),
        "tally/accounts.py": r_accounts(s),
        "tally/dates.py": r_dates(s),
        "tally/money.py": r_money(s),
        "tally/periods.py": r_periods(s),
        "tally/report.py": r_report(s),
        "tally/io/__init__.py": "",
        "tally/io/readers.py": r_readers(s),
        "tally/data/__init__.py": "",
        "tally/data/currencies.py": r_currencies(s),
        "tally/formats/__init__.py": r_formats_init(s),
        "tally/formats/csvfmt.py": r_csvfmt(s),
        "tally/formats/jsonfmt.py": JSONFMT,
        "tests/test_money.py": r_test_money(s),
        "tests/test_periods.py": r_test_periods(s),
        "tests/test_readers.py": r_test_readers(s),
        "tests/test_export.py": r_test_export(s),
        "tests/test_formats.py": r_test_formats(s),
    }
    for n in s["formats"]:
        files[f"tally/formats/fmt_{n}.py"] = r_format(n)
    files["tally/rates.py" if s["rates_path"] == "tally" else "tally/data/rates.py"] = r_rates(s)
    return files
