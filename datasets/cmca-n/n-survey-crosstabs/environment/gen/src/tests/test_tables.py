"""Runs bin/crosstabs.py on each small survey under tests/fixtures and compares
the tables file with the reviewed one next to it, to 0.01 as docs/output.md 4.2
says.

From /app: python -m unittest discover -s tests -t .
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "bin" / "crosstabs.py"
FIXTURES = HERE / "fixtures"
COUNTS = ("rows", "duplicates", "short_partials", "speeders", "complete", "partial")


def build(case):
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "tables.json"
        p = subprocess.run([sys.executable, str(SCRIPT), str(FIXTURES / case / "input"), str(out)],
                           capture_output=True, text=True, timeout=120)
        if p.returncode:
            raise AssertionError(f"crosstabs.py exited with status {p.returncode}:\n{p.stderr[-2000:]}")
        return json.loads(out.read_text(encoding="utf-8"))


def agrees(got, want):
    if got is None or want is None:
        return got is None and want is None
    if isinstance(got, bool) or not isinstance(got, (int, float)):
        return False
    return abs(got - want) <= 0.011


def is_count(v):
    return isinstance(v, int) and not isinstance(v, bool)


def first_difference(got, want):
    if not isinstance(got, dict) or set(got) != {"survey", "summary", "tables"}:
        return "the output is not an object with exactly the keys survey, summary and tables"
    if got["survey"] != want["survey"]:
        return f"survey {got['survey']!r}, expected {want['survey']!r}"
    s, w = got["summary"], want["summary"]
    if not isinstance(s, dict) or set(s) != set(w):
        return f"summary keys {sorted(s) if isinstance(s, dict) else s!r}, expected {sorted(w)}"
    versions = s["versions"] if isinstance(s["versions"], list) else []
    if [v.get("version") if isinstance(v, dict) else None for v in versions] != [v["version"] for v in w["versions"]]:
        return f"summary versions {versions!r}, expected versions {[v['version'] for v in w['versions']]}"
    for g, e in zip(versions, w["versions"]):
        if set(g) != set(e):
            return f"summary version {e['version']}: keys {sorted(g)}, expected {sorted(e)}"
        for k in COUNTS:
            if not is_count(g[k]) or g[k] != e[k]:
                return f"summary version {e['version']} {k}: {g[k]!r}, expected {e[k]}"
    if not is_count(s["respondents"]) or s["respondents"] != w["respondents"]:
        return f"summary respondents: {s['respondents']!r}, expected {w['respondents']}"
    for k in ("effective_n", "weight_min", "weight_max"):
        if not agrees(s[k], w[k]):
            return f"summary {k}: {s[k]!r}, expected {w[k]}"
    tables = got["tables"] if isinstance(got["tables"], list) else []
    ids = [t.get("table") if isinstance(t, dict) else None for t in tables]
    if ids != [t["table"] for t in want["tables"]]:
        return f"tables {ids}, expected {[t['table'] for t in want['tables']]}"
    for t, e in zip(tables, want["tables"]):
        if set(t) != {"table", "columns"} or not isinstance(t["columns"], list):
            return f"table {e['table']}: not an object with exactly the keys table and columns"
        cols = [c.get("column") if isinstance(c, dict) else None for c in t["columns"]]
        if cols != [c["column"] for c in e["columns"]]:
            return f"table {e['table']}: columns {cols}, expected {[c['column'] for c in e['columns']]}"
        for c, ec in zip(t["columns"], e["columns"]):
            where = f"table {e['table']} column {ec['column']}"
            if set(c) != {"column", "base", "weighted_base", "values"}:
                return f"{where}: keys {sorted(c)}, expected column, base, weighted_base, values"
            if not is_count(c["base"]) or c["base"] != ec["base"]:
                return f"{where} base: {c['base']!r}, expected {ec['base']}"
            if not agrees(c["weighted_base"], ec["weighted_base"]):
                return f"{where} weighted_base: {c['weighted_base']!r}, expected {ec['weighted_base']}"
            values = c["values"] if isinstance(c["values"], dict) else {}
            if set(values) != set(ec["values"]):
                return f"{where}: value keys {sorted(values)}, expected {sorted(ec['values'])}"
            for k, v in ec["values"].items():
                if not agrees(values[k], v):
                    return f"{where} value {k}: {values[k]!r}, expected {v}"
    return None


class Tables(unittest.TestCase):
    def check(self, case):
        want = json.loads((FIXTURES / case / "expected.json").read_text(encoding="utf-8"))
        problem = first_difference(build(case), want)
        self.assertIsNone(problem, problem)

    def test_form_versions(self):
        self.check("versions")

    def test_routing_and_partials(self):
        self.check("routing")

    def test_duplicates_and_speeders(self):
        self.check("cleaning")

    def test_weighting(self):
        self.check("weighting")


if __name__ == "__main__":
    unittest.main()
