"""Runs bin/fees.py on each small input under tests/fixtures and compares the
statements file with the reviewed one next to it.

From /app: python -m unittest discover -s tests -t .
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "bin" / "fees.py"
FIXTURES = HERE / "fixtures"


def build(case):
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "statements.json"
        p = subprocess.run([sys.executable, str(SCRIPT), str(FIXTURES / case / "input"), str(out)],
                           capture_output=True, text=True, timeout=120)
        if p.returncode:
            raise AssertionError(f"fees.py exited with status {p.returncode}:\n{p.stderr[-2000:]}")
        return json.loads(out.read_text(encoding="utf-8"))


def first_difference(got, want):
    if not isinstance(got, dict):
        return "the output is not a JSON object"
    for key in ("library", "period"):
        if got.get(key) != want[key]:
            return f"{key}: {got.get(key)!r}, expected {want[key]!r}"
    statements = got.get("statements")
    if not isinstance(statements, list):
        return "statements is not a list"
    names = [s.get("patron") if isinstance(s, dict) else None for s in statements]
    expected = [s["patron"] for s in want["statements"]]
    if names != expected:
        return f"statements for {names}, expected {expected}"
    for s, w in zip(statements, want["statements"]):
        loans = s.get("loans")
        if not isinstance(loans, list):
            return f"{w['patron']}: loans is not a list"
        ids = [x.get("loan") if isinstance(x, dict) else None for x in loans]
        if ids != [x["loan"] for x in w["loans"]]:
            return f"{w['patron']}: loans {ids}, expected {[x['loan'] for x in w['loans']]}"
        for x, e in zip(loans, w["loans"]):
            if x != e:
                return f"{w['patron']} loan {e['loan']}: {x}, expected {e}"
        if s != w:
            return f"{w['patron']}: {dict((k, v) for k, v in s.items() if k != 'loans')}, expected " \
                   f"{dict((k, v) for k, v in w.items() if k != 'loans')}"
    if got.get("branches") != want["branches"]:
        return f"branches: {got.get('branches')}, expected {want['branches']}"
    if set(got) != set(want):
        return f"top-level keys {sorted(got)}, expected {sorted(want)}"
    return None


class Fees(unittest.TestCase):
    def check(self, case):
        want = json.loads((FIXTURES / case / "expected.json").read_text(encoding="utf-8"))
        problem = first_difference(build(case), want)
        self.assertIsNone(problem, problem)

    def test_grace_caps_and_discounts(self):
        self.check("basic")

    def test_closed_days(self):
        self.check("calendar")

    def test_export_files_and_events(self):
        self.check("exports")

    def test_waivers_categories_and_rounding(self):
        self.check("money")


if __name__ == "__main__":
    unittest.main()
