"""Runs bin/hourly.py on each small input under tests/fixtures and compares the
hourly file with the reviewed one next to it, to 0.01 as docs/output.md 3.3
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
SCRIPT = HERE.parent / "bin" / "hourly.py"
FIXTURES = HERE / "fixtures"
QUANTITIES = ("temp", "rh", "pres", "wspd", "wdir", "rain")


def build(case):
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "hourly.json"
        p = subprocess.run([sys.executable, str(SCRIPT), str(FIXTURES / case / "input"), str(out)],
                           capture_output=True, text=True, timeout=120)
        if p.returncode:
            raise AssertionError(f"hourly.py exited with status {p.returncode}:\n{p.stderr[-2000:]}")
        return json.loads(out.read_text(encoding="utf-8"))


def agrees(q, got, want):
    if got is None or want is None:
        return got is None and want is None
    if isinstance(got, bool) or not isinstance(got, (int, float)):
        return False
    d = abs(got - want)
    if q == "wdir":
        d = min(d % 360, 360 - d % 360)
    return d <= 0.011


def first_difference(got, want):
    if not isinstance(got, dict) or not isinstance(got.get("stations"), list):
        return "the output is not an object with a stations list"
    ids = [s.get("station") for s in got["stations"]]
    want_ids = [s["station"] for s in want["stations"]]
    if ids != want_ids:
        return f"stations {ids}, expected {want_ids}"
    for s, w in zip(got["stations"], want["stations"]):
        if s.get("interval_s") != w["interval_s"]:
            return f"{w['station']}: interval_s {s.get('interval_s')!r}, expected {w['interval_s']!r}"
        hours = [h.get("hour") for h in s.get("hours", [])]
        want_hours = [h["hour"] for h in w["hours"]]
        if hours != want_hours:
            return f"{w['station']}: hours {hours}, expected {want_hours}"
        for h, e in zip(s["hours"], w["hours"]):
            for q in QUANTITIES:
                g = h.get(q)
                if not isinstance(g, dict) or set(g) != {"value", "n"}:
                    return f"{w['station']} {e['hour']} {q}: {g!r} is not an object with value and n"
                if g["n"] != e[q]["n"] or not agrees(q, g["value"], e[q]["value"]):
                    return f"{w['station']} {e['hour']} {q}: {g}, expected {e[q]}"
    return None


class Hourly(unittest.TestCase):
    def check(self, case):
        want = json.loads((FIXTURES / case / "expected.json").read_text(encoding="utf-8"))
        problem = first_difference(build(case), want)
        self.assertIsNone(problem, problem)

    def test_units_coverage_and_direction(self):
        self.check("basic")

    def test_clock_drift(self):
        self.check("drift")

    def test_reissued_rows(self):
        self.check("reissue")

    def test_rain_counter(self):
        self.check("rain")


if __name__ == "__main__":
    unittest.main()
