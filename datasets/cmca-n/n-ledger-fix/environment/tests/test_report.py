"""Reports for every statement under data/statements must match tests/expected/<name>.json."""
import json
import unittest
from pathlib import Path

from ledger.rates import load_rates
from ledger.report import build_report
from ledger.statement import read_statement

ROOT = Path(__file__).resolve().parent.parent
STATEMENTS = sorted((ROOT / "data" / "statements").glob("*.csv"))
EXPECTED = Path(__file__).resolve().parent / "expected"


class StatementReportsTest(unittest.TestCase):
    def test_every_statement_has_an_expected_report(self):
        self.assertTrue(STATEMENTS)
        self.assertEqual(sorted(p.stem for p in STATEMENTS), sorted(p.stem for p in EXPECTED.glob("*.json")))

    def test_reports(self):
        rates = load_rates(ROOT / "data" / "rates.csv")
        for path in STATEMENTS:
            with self.subTest(statement=path.name):
                expected = json.loads((EXPECTED / f"{path.stem}.json").read_text())
                self.assertEqual(build_report(read_statement(path), rates), expected)


if __name__ == "__main__":
    unittest.main()
