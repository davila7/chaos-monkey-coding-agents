"""Builds /app: the tally repository with its history under repo/ and a user report under reports/.

Usage: python3 build.py OUT_DIR

The history is a fixed sequence of states rendered by project.py and committed with fixed
authors and dates, so commit ids are the same on every run. Before it finishes, the script runs
the report command of the issue at every commit between the two releases and asserts the planned
story (which commits match the good output, the reported output, or neither).
"""
import os
import random
import shutil
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import project  # noqa: E402

SEED = 40427
MONTH = "2026-03"
PRE = 110      # commits from the first import to v2.3.0
RANGE = 180    # commits from v2.3.0 to v2.4.0
POST = 14      # commits after v2.4.0
# Planted commits, as positions after v2.3.0.
EVENTS = {
    20: "bom", 35: "release:2.3.1", 40: "export_header", 58: "month_bounds", 63: "blank", 70: "grouping",
    78: "release:2.3.2", 84: "move_rates", 97: "fix_import", 100: "amount_bug", 105: "upper_currency",
    46: "parse_dt", 88: "parse_dtz", 112: "amount_fix", 116: "export_seconds", 121: "culprit", 127: "offsets_note", 140: "release:2.4.0rc1", 150: "memo",
    RANGE: "release:2.4.0",
}
PRE_RELEASES = {40: "2.1.0", 75: "2.2.0", 92: "2.2.1", PRE: "2.3.0"}

AUTHORS = [("Mira Okafor", "mira@ledgerworks.example", -5), ("Jonas Weber", "jonas@ledgerworks.example", 1),
           ("Priya Raman", "priya@ledgerworks.example", 5.5), ("Tom Abbott", "tom@ledgerworks.example", 0),
           ("Lucia Ferraro", "lucia@ledgerworks.example", 1), ("Dan Kowalski", "dan@ledgerworks.example", -8)]

CURRENCY_POOL = [
    ("AUD", "Australian dollar", 2), ("NZD", "New Zealand dollar", 2), ("SEK", "Swedish krona", 2),
    ("NOK", "Norwegian krone", 2), ("DKK", "Danish krone", 2), ("PLN", "Zloty", 2), ("CZK", "Czech koruna", 2),
    ("HUF", "Forint", 2), ("RON", "Romanian leu", 2), ("BGN", "Bulgarian lev", 2), ("ISK", "Iceland krona", 0),
    ("TRY", "Turkish lira", 2), ("ILS", "New Israeli sheqel", 2), ("ZAR", "Rand", 2), ("MXN", "Mexican peso", 2),
    ("BRL", "Brazilian real", 2), ("ARS", "Argentine peso", 2), ("CLP", "Chilean peso", 0),
    ("COP", "Colombian peso", 2), ("PEN", "Sol", 2), ("UYU", "Peso uruguayo", 2), ("INR", "Indian rupee", 2),
    ("PKR", "Pakistan rupee", 2), ("LKR", "Sri Lanka rupee", 2), ("BDT", "Taka", 2), ("NPR", "Nepalese rupee", 2),
    ("CNY", "Yuan renminbi", 2), ("HKD", "Hong Kong dollar", 2), ("TWD", "New Taiwan dollar", 2),
    ("KRW", "Won", 0), ("SGD", "Singapore dollar", 2), ("MYR", "Malaysian ringgit", 2), ("THB", "Baht", 2),
    ("IDR", "Rupiah", 2), ("PHP", "Philippine peso", 2), ("VND", "Dong", 0), ("AED", "UAE dirham", 2),
    ("SAR", "Saudi riyal", 2), ("QAR", "Qatari rial", 2), ("KWD", "Kuwaiti dinar", 3), ("BHD", "Bahraini dinar", 3),
    ("OMR", "Rial Omani", 3), ("JOD", "Jordanian dinar", 3), ("EGP", "Egyptian pound", 2), ("MAD", "Moroccan dirham", 2),
    ("TND", "Tunisian dinar", 3), ("KES", "Kenyan shilling", 2), ("NGN", "Naira", 2), ("GHS", "Ghana cedi", 2),
    ("UGX", "Uganda shilling", 0), ("TZS", "Tanzanian shilling", 2), ("XOF", "CFA franc BCEAO", 0),
    ("UAH", "Hryvnia", 2), ("GEL", "Lari", 2), ("KZT", "Tenge", 2), ("RSD", "Serbian dinar", 2),
]
ALIAS_WORDS = ["ATLAS", "BIRCH", "CEDAR", "DELTA", "EMBER", "FJORD", "GROVE", "HAVEN", "IVORY", "JUNIPER", "KESTREL",
               "LUMEN", "MAPLE", "NORTHWIND", "ONYX", "PRAIRIE", "QUARRY", "RAVEN", "SIERRA", "TIMBER", "UMBER",
               "VALE", "WILLOW", "YARROW", "ZEPHYR", "ASPEN", "BASALT", "COVE", "DUNE", "ESKER"]
ACCOUNTS = ["OPS-EAST", "OPS-WEST", "SALES-NA", "SALES-EU", "SUPPORT", "R-AND-D", "FACILITIES", "TRAVEL"]
USAGE_POOL = [
    ("explain the --account filter", "`--account` limits a report to one account; the name is compared in upper case."),
    ("describe several input files", "Several ledger files can be given; their rows are added together."),
    ("note the TOTAL line", "The `TOTAL` line is the sum of the account lines, after conversion."),
    ("mention --base", "`--base EUR` converts every amount to euros before summing."),
    ("document exit status", "The exit status is 0 on success and 2 for usage errors."),
    ("list export formats", "`tally formats` lists every export format of the installed release."),
    ("note rate tables", "Exchange rates are fixed per release and listed in the changelog when they change."),
    ("explain empty months", "A month without rows prints only the header and a zero `TOTAL`."),
    ("describe currencies command", "`tally currencies` prints code, minor units and name of each known currency."),
    ("mention retired accounts", "Retired account names are reported under the name that replaced them."),
    ("note sorting", "Accounts are listed in alphabetical order."),
    ("describe exports to stdout", "Exports are written to standard output; redirect them to a file."),
    ("note encoding", "Ledger files are read as UTF-8."),
    ("document version flag", "`tally --version` prints the release."),
    ("clarify amount width", "Report amounts are right-aligned in a 14-character column."),
    ("explain negative totals", "Refunds and reversals can make an account total negative."),
    ("note month format", "Months are written `YYYY-MM`; `2026-3` is not accepted."),
    ("describe json export", "The `json` export writes one array; `ndjson` writes one object per line."),
]
DEV_POOL = [
    ("Note how to run one test module", "Run one module with `python -m unittest tests.test_money`."),
    ("Ask for changelog entries", "User-visible changes get a line in CHANGELOG.md under the next release."),
    ("Describe release steps", "A release bumps the version in pyproject.toml and tally/__init__.py and tags `vX.Y.Z`."),
    ("Prefer Decimal for amounts", "Amounts are Decimal end to end; never convert them to float."),
    ("Keep the standard library only", "Do not add dependencies; the tool runs on a bare Python install."),
    ("Describe export modules", "An export format is a module under tally/formats with a `write(rows, fh)` function."),
    ("Document commit style", "Commit subjects are imperative and under 72 characters."),
    ("Note test data", "Tests build their rows in code; there are no fixture files."),
    ("Mention line length", "Lines stay under 110 characters."),
    ("Note rate updates", "Rate updates are their own commits so they are easy to find."),
    ("Describe CLI layout", "Each command is a `cmd_*` function in tally/cli.py listed in `COMMANDS`."),
    ("Mention release candidates", "Release candidates are tagged `vX.Y.ZrcN` from the main branch."),
]
DOCSTRING_SUBJECTS = ["Reword docstring of {f}", "Clarify {f} docstring", "Docs: tighten the description of {f}"]
HELP_SUBJECTS = ["Clarify help text of {c} --{o}", "Reword --{o} help", "Shorter help for {c} --{o}"]
HELP_MAIN_SUBJECTS = ["Reword the program description", "Clarify what tally does in --help"]
FILLER_KINDS = [("currency", 16), ("format", 9), ("format_test", 7), ("alias", 12), ("usage", 9), ("dev", 6),
                ("doc", 18), ("help", 12)]


class History:
    def __init__(self, repo, rng):
        self.repo = repo
        self.rng = rng
        self.when = datetime(2025, 7, 7, 9, 0, tzinfo=timezone.utc)
        self.commits = []   # (sha, subject)
        self.tags = {}
        self.env = dict(os.environ, HOME=str(repo.parent / "home"), GIT_CONFIG_NOSYSTEM="1",
                        GIT_CONFIG_GLOBAL=os.devnull, TZ="UTC", LC_ALL="C")

    def git(self, *args, env=None):
        p = subprocess.run(["git", *args], cwd=self.repo, env=env or self.env, capture_output=True, text=True)
        if p.returncode:
            raise RuntimeError(f"git {' '.join(args)}: {p.stderr}")
        return p.stdout.strip()

    def write(self, files):
        current = {str(p.relative_to(self.repo)) for p in self.repo.rglob("*")
                   if p.is_file() and ".git" not in p.relative_to(self.repo).parts}
        for rel in current - set(files):
            (self.repo / rel).unlink()
        for rel, text in files.items():
            path = self.repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists() or path.read_text() != text:
                path.write_text(text)
        for d in sorted((p for p in self.repo.rglob("*") if p.is_dir() and ".git" not in p.parts), reverse=True):
            if not any(d.iterdir()):
                d.rmdir()

    def commit(self, state, subject, body=""):
        self.write(project.render(state))
        self.when += timedelta(minutes=self.rng.randint(40, 2200))
        name, email, off = AUTHORS[self.rng.randrange(len(AUTHORS))]
        tz = timezone(timedelta(hours=off))
        stamp = self.when.astimezone(tz).strftime("%Y-%m-%dT%H:%M:%S%z")
        env = dict(self.env, GIT_AUTHOR_NAME=name, GIT_AUTHOR_EMAIL=email, GIT_AUTHOR_DATE=stamp,
                   GIT_COMMITTER_NAME=name, GIT_COMMITTER_EMAIL=email, GIT_COMMITTER_DATE=stamp)
        self.git("add", "-A", env=env)
        msg = subject + ("\n\n" + body if body else "")
        self.git("commit", "-q", "-m", msg, env=env)
        sha = self.git("rev-parse", "HEAD")
        self.commits.append((sha, subject))
        self.last_env = env
        return sha

    def tag(self, name):
        self.git("tag", "-a", name, "-m", f"tally {name[1:]}", env=self.last_env)
        self.tags[name] = self.commits[-1][0]


def filler(state, rng, pools):
    """Applies one ordinary change to state and returns its commit subject and body."""
    while True:
        kind = rng.choices([k for k, _ in FILLER_KINDS], [w for _, w in FILLER_KINDS])[0]
        if kind == "currency" and pools["currency"]:
            code, name, minor = pools["currency"].pop(0)
            state["currencies"].append((code, name, minor))
            return f"Add {code} ({name}) to the currency table", ""
        if kind == "format" and pools["format"]:
            n = pools["format"].pop(0)
            state["formats"].append(n)
            return f"Add {n} export format", f"{project.FORMAT_INFO[n][2]}, written by `tally export --format {n}`."
        if kind == "format_test":
            untested = [n for n in state["formats"] if n not in state["format_tests"]]
            if untested:
                n = untested[0]
                state["format_tests"].append(n)
                return f"Test the {n} writer", ""
        if kind == "alias" and pools["alias"]:
            old, new = pools["alias"].pop(0)
            state["aliases"].append((old, new))
            return f"Map retired account {old} to {new}", ""
        if kind == "usage" and pools["usage"]:
            topic, text = pools["usage"].pop(0)
            state["usage_notes"].append(text)
            return f"Docs: {topic}", ""
        if kind == "dev" and pools["dev"]:
            subject, text = pools["dev"].pop(0)
            state["dev_notes"].append(text)
            return subject, ""
        if kind == "doc":
            f = rng.choice(sorted(project.DOCSTRINGS))
            state["doc"][f] += 1
            return rng.choice(DOCSTRING_SUBJECTS).format(f=f), ""
        if kind == "help":
            key = rng.choice(sorted(project.HELP))
            state["help"][key] += 1
            if key[0] == "tally":
                return rng.choice(HELP_MAIN_SUBJECTS), ""
            return rng.choice(HELP_SUBJECTS).format(c=key[0], o=key[1]), ""


def changelog_add(state, entry):
    state["changelog"][-1][1].append(entry)


def release(state, ver):
    state["version"] = ver
    state["changelog"][-1] = (ver, state["changelog"][-1][1] or ["Maintenance release."])
    subject = f"Release {ver}"
    return subject


def planted(state, event):
    """Applies a planted change; returns (subject, body)."""
    if event == "bom":
        state["readers_bom"] = True
        changelog_add(state, "Ledgers saved with a byte order mark are read correctly.")
        return "Accept ledgers saved with a byte order mark", "Spreadsheet exports on Windows start with one."
    if event == "export_header":
        state["export_header"] = "date"
        changelog_add(state, "CSV exports name the booking date column `date`.")
        return "Rename export column when to date", "The column holds the booking date, not a time."
    if event == "month_bounds":
        state["month_bounds"] = "calendar"
        return ("Fix month-end boundary in period filter",
                "Use calendar.monthrange for the last day instead of stepping back from the next month.")
    if event == "blank":
        state["readers_blank"] = True
        changelog_add(state, "Blank lines in ledgers are skipped.")
        return "Skip blank lines in ledgers", ""
    if event == "grouping":
        state["grouping"] = True
        changelog_add(state, "Report amounts use thousands separators.")
        return "Show thousands separators in report totals", ""
    if event == "move_rates":
        state["rates_path"] = "data"
        return "Move exchange rates under tally/data", "Rates and currencies are data; keep them together."
    if event == "fix_import":
        state["report_import"] = "data"
        return "Fix report import after moving rates", ""
    if event == "amount_bug":
        state["amount"] = "bug"
        changelog_add(state, "Amounts may carry a leading plus sign or a currency symbol.")
        return "Accept a leading plus sign and currency symbols in amounts", ""
    if event == "upper_currency":
        state["readers_upper_currency"] = True
        return "Normalize currency codes to upper case", ""
    if event == "amount_fix":
        state["amount"] = "fixed"
        return "Keep parenthesized amounts negative", "The sign check ran after the parentheses were stripped."
    if event == "culprit":
        state["parse_when"] = "utc"
        state["report_rename"] = True
        state["test_readers_z"] = True
        changelog_add(state, "Internal: one timestamp parser for imports and exports.")
        return ("Share timestamp parsing between readers and exports",
                "The CSV export already parses with tally.dates.to_instant; use it in the readers too instead\n"
                "of a second ISO 8601 parser, and give the report accumulator a clearer name.")
    if event == "offsets_note":
        state["offsets_note"] = True
        return "Docs: give examples of offsets in the when column", ""
    if event == "parse_dt":
        state["parse_when"] = "dt"
        return "Parse when values with datetime.fromisoformat", "One parser for dates and date-times."
    if event == "parse_dtz":
        state["parse_when"] = "dtz"
        return "Accept a trailing Z in when values", "Some bank exports write UTC times with a Z suffix."
    if event == "export_seconds":
        state["export_seconds"] = True
        changelog_add(state, "CSV exports write `when_utc` to the second.")
        return "Write UTC timestamps in exports to the second", ""
    if event == "memo":
        state["readers_memo_strip"] = True
        return "Trim whitespace around memos", ""
    raise ValueError(event)


def build_history(repo):
    rng = random.Random(SEED)
    pools = {
        "currency": list(CURRENCY_POOL),
        "format": [n for n, _, _, _ in project.FORMATS],
        "alias": [(f"{w}-{rng.choice(['OLD', 'LEGACY', 'X'])}", rng.choice(ACCOUNTS[:4] + ["ADMIN", "MARKETING"]))
                  for w in ALIAS_WORDS],
        "usage": list(USAGE_POOL),
        "dev": list(DEV_POOL),
    }
    repo.mkdir(parents=True)
    template = repo.parent / "empty-template"
    template.mkdir()
    h = History(repo, rng)
    h.git("init", "-q", f"--template={template}", "-b", "main")
    shutil.rmtree(template)
    state = project.initial_state()
    h.commit(state, "Import tally 2.0", "Monthly totals and exports for CSV ledgers.")
    h.tag("v2.0.0")
    state["changelog"].append(("Unreleased", []))
    for i in range(1, PRE + 1):
        if i in PRE_RELEASES:
            h.commit(state, release(state, PRE_RELEASES[i]))
            h.tag("v" + PRE_RELEASES[i])
            state["changelog"].append(("Unreleased", []))
            continue
        subject, body = filler(state, rng, pools)
        h.commit(state, subject, body)
    base = len(h.commits) - 1
    for pos in range(1, RANGE + POST + 1):
        event = EVENTS.get(pos)
        if event and event.startswith("release:"):
            ver = event.split(":")[1]
            h.commit(state, release(state, ver))
            h.tag("v" + ver)
            state["changelog"].append(("Unreleased", []))
            continue
        if event:
            subject, body = planted(state, event)
        else:
            subject, body = filler(state, rng, pools)
        h.commit(state, subject, body)
    return h, base


# The user's ledger.

def ledger(rng):
    offsets = ["-08:00", "-07:00", "-05:00", "-04:00", "+00:00", "+01:00", "+05:30", "Z"]
    rows = ["id,when,account,amount,currency,memo"]
    day = date(2026, 2, 16)
    n = 0
    memos = ["fuel", "hotel", "client lunch", "software", "freight", "courier", "parts", "repairs", "rent",
             "utilities", "conference", "training", "cloud hosting", "printing", "taxi", "refund"]
    while day <= date(2026, 4, 12):
        edge = day.day in (1, 28, 31) or (day.month == 3 and day.day == 1)
        for _ in range(rng.randint(28, 40) + (18 if edge else 0)):
            n += 1
            acct = rng.choice(ACCOUNTS)
            r = rng.random()
            if r < 0.35:
                when = day.isoformat()
            else:
                hh = rng.choice([22, 23, 23, 0, 1]) if edge and rng.random() < 0.6 else rng.randint(6, 21)
                when = f"{day.isoformat()}T{hh:02d}:{rng.randint(0, 59):02d}:{rng.randint(0, 59):02d}"
                when += rng.choice(offsets)
            cents = rng.randint(250, 480000)
            amount = Decimal(cents) / 100
            text = f"{amount:,.2f}" if rng.random() < 0.7 else f"{amount:.2f}"
            memo = rng.choice(memos)
            if rng.random() < 0.09:
                text = f"({text})"
                memo = "refund"
            elif rng.random() < 0.03:
                text = f"-{text}"
                memo = "reversal"
            if "," in text:
                text = f'"{text}"'
            rows.append(f"T{n:05d},{when},{acct},{text},USD,{memo}")
        day += timedelta(days=1)
    return "\n".join(rows) + "\n"


def run_report(repo, ledger_path, env):
    p = subprocess.run([sys.executable, "-m", "tally", "report", "--month", MONTH, str(ledger_path)], cwd=repo,
                       env=dict(env, PYTHONDONTWRITEBYTECODE="1"), capture_output=True, text=True)
    if p.returncode:
        return None, p.stderr
    return p.stdout, None


def numbers(text):
    out = {}
    for line in text.splitlines()[1:]:
        name, value = line.split()
        out[name] = Decimal(value.replace(",", ""))
    return out


def check_story(h, base, ledger_path):
    repo = h.repo
    outputs = {}
    for pos in range(0, RANGE + 1):
        sha = h.commits[base + pos][0]
        h.git("checkout", "-q", sha)
        out, err = run_report(repo, ledger_path, h.env)
        outputs[pos] = (out, err)
    good = numbers(outputs[0][0])
    bad = numbers(outputs[RANGE][0])
    assert good != bad
    culprit = next(p for p, e in EVENTS.items() if e == "culprit")
    for pos, (out, err) in outputs.items():
        if 84 <= pos < 97:
            assert out is None and "ModuleNotFoundError" in err, pos
            continue
        assert out is not None, (pos, err)
        got = numbers(out)
        if 100 <= pos < 112:
            assert got != good and got != bad, pos
        elif pos < culprit:
            assert got == good, pos
        else:
            assert got == bad, pos
        assert ("," in out) == (pos >= 70), pos
    # The repository's own tests: green at v2.3.0, red from the export header change on.
    for pos, ok in ((0, True), (39, True), (40, False), (culprit - 1, False), (culprit, False), (RANGE, False)):
        h.git("checkout", "-q", h.commits[base + pos][0])
        p = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], cwd=repo,
                           env=dict(h.env, PYTHONDONTWRITEBYTECODE="1"), capture_output=True, text=True)
        assert (p.returncode == 0) == ok, (pos, p.stderr[-800:])
    h.git("checkout", "-q", "main")
    return outputs


def issue_text(good_out, bad_out):
    good_out = good_out.rstrip("\n")
    bad_out = bad_out.rstrip("\n")
    indent = lambda t: "\n".join("    " + line for line in t.splitlines())  # noqa: E731
    return f"""# Monthly totals changed after upgrading to 2.4.0

Opened by: Hanna Lindqvist (finance operations)
Label: bug

We upgraded tally from 2.3.0 to 2.4.0 last week. Since then the March report for our ledger no
longer agrees with our books. We ran the same command with both releases on the same file
(attached as `ledger.csv`), from a checkout of each release tag:

    python -m tally report --month 2026-03 ledger.csv

With 2.3.0:

{indent(good_out)}

With 2.4.0:

{indent(bad_out)}

The 2.3.0 figures are the ones our accountants signed off. Nothing changed on our side: same file,
same command, same machine. We did not try the releases in between.
"""


def main():
    out = Path(sys.argv[1])
    if out.exists():
        raise SystemExit(f"{out} exists")
    work = out.parent / (out.name + ".work")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    rng = random.Random(SEED + 1)
    reports = work / "reports" / "issue-412"
    reports.mkdir(parents=True)
    (reports / "ledger.csv").write_text(ledger(rng))
    h, base = build_history(work / "repo")
    outputs = check_story(h, base, reports / "ledger.csv")
    (reports / "issue.md").write_text(issue_text(outputs[0][0], outputs[RANGE][0]))
    # The index holds file times; rebuild it without them so two builds give the same bytes.
    (h.repo / ".git" / "index").unlink()
    h.git("read-tree", "HEAD")
    # Reflogs record the time of each checkout above.
    shutil.rmtree(h.repo / ".git" / "logs")
    shutil.rmtree(work / "home", ignore_errors=True)
    work.rename(out)


if __name__ == "__main__":
    main()
