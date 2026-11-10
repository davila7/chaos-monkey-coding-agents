"""The command line against the reviewed outputs in tests/expected."""

import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXPECTED = ROOT / "tests" / "expected"


def run(*args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run([sys.executable, "-m", "meterbill", *args], cwd=ROOT, env=env, capture_output=True, text=True)


class ReviewedOutputs(unittest.TestCase):
    def check(self, name: str, *args: str) -> None:
        r = run(*args)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, (EXPECTED / name).read_text())

    def test_bills(self):
        for path in sorted((ROOT / "samples" / "accounts").glob("*.json")):
            with self.subTest(account=path.stem):
                self.check(f"bill-{path.stem}.txt", "bill", f"samples/accounts/{path.name}")
                self.check(f"bill-{path.stem}.json", "bill", f"samples/accounts/{path.name}", "--format", "json")

    def test_bill_csv(self):
        self.check("bill-a-1001.csv", "bill", "samples/accounts/a-1001.json", "--format", "csv")

    def test_batch(self):
        self.check("batch.txt", "batch", "samples/accounts")
        self.check("batch.csv", "batch", "samples/accounts", "--format", "csv", "--workers", "2")

    def test_quotes(self):
        self.check("quote-home-2.txt", "quote", "home-2", "250.5", "30")
        self.check("quote-flex-ch.json", "quote", "flex-ch", "1234.5", "91", "--format", "json")
        self.check("quote-villa-se.txt", "quote", "villa-se", "812.3", "30")
        self.check("quote-uk-std.txt", "quote", "uk-std", "0", "31")

    def test_tariffs(self):
        self.check("tariffs.txt", "tariffs")


class Errors(unittest.TestCase):
    def test_unknown_tariff(self):
        r = run("quote", "home-9", "10", "30")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stderr, "meterbill: error: unknown tariff 'home-9' (known: flex-ch, home-1, home-2, shop-ch, uk-std, villa-se)\n")

    def test_bad_days(self):
        r = run("quote", "home-1", "10", "0")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stderr, "meterbill: error: days must be at least 1\n")

    def test_missing_account(self):
        r = run("bill", "samples/accounts/nope.json")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stderr, "meterbill: error: nope.json: No such file or directory\n")


if __name__ == "__main__":
    unittest.main()
