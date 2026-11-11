"""The command line against the reviewed outputs in tests/expected."""

import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXPECTED = ROOT / "tests" / "expected"
SITES = ["north", "south"]


def run(*args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run([sys.executable, "-m", "deskstats", *args], cwd=ROOT, env=env, capture_output=True, text=True)


class ReviewedOutputs(unittest.TestCase):
    def check(self, name: str, *args: str) -> None:
        r = run(*args)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, (EXPECTED / name).read_text())

    def test_reports(self):
        for site in SITES:
            for path in sorted(EXPECTED.glob(f"*-{site}.*")):
                command = path.name.split("-", 1)[0]
                extra = [] if path.suffix == ".txt" else ["--format", path.suffix[1:]]
                with self.subTest(report=path.name):
                    self.check(path.name, command, f"samples/{site}", *extra)

    def test_windows(self):
        self.check("daily-north-mar03-mar05.txt", "daily", "samples/north", "--since", "2026-03-03", "--until", "2026-03-05")
        self.check("tickets-south-until-mar12.csv", "tickets", "samples/south", "--until", "2026-03-12", "--format", "csv")
        self.check("calls-north-since-mar06.txt", "calls", "samples/north", "--since", "2026-03-06")

    def test_warnings(self):
        r = run("calls", "samples/north")
        self.assertEqual(r.stderr, "tickets.csv:26: bad time, row skipped\n")


class Errors(unittest.TestCase):
    def test_missing_folder(self):
        r = run("daily", "samples/nowhere")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stderr, "deskstats: error: samples/nowhere: not a folder\n")

    def test_since_after_until(self):
        r = run("daily", "samples/north", "--since", "2026-03-05", "--until", "2026-03-04")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stderr, "deskstats: error: --since is after --until\n")

    def test_not_a_date(self):
        r = run("daily", "samples/north", "--since", "03/04/2026")
        self.assertEqual(r.returncode, 2)
        self.assertTrue(r.stderr.endswith("deskstats: error: argument --since: not a date: '03/04/2026'\n"), r.stderr)


if __name__ == "__main__":
    unittest.main()
