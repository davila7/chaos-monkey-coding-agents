import unittest
from decimal import Decimal

from quoter import settings
from quoter.core.errors import InputError, SettingsError
from quoter.services.batch import run_batch
from tests.helpers import MISSING_COLUMN, SMALL_BATCH, SettingsCase, write_temp


class BatchTest(SettingsCase):
    def test_lines_and_errors(self):
        result = run_batch(write_temp(self, SMALL_BATCH, ".csv"))
        self.assertEqual([l.ident for l in result.lines], ["A1", "A2", "A3", "A4", "A5", "A6"])
        self.assertIsNone(result.lines[3].quote)
        self.assertIn("unknown country", result.lines[3].error)
        self.assertEqual(result.lines[0].quote, result.lines[4].quote)

    def test_totals(self):
        result = run_batch(write_temp(self, SMALL_BATCH, ".csv"))
        quoted = [l.quote for l in result.lines if l.quote]
        self.assertEqual(result.net_total, sum(q.net for q in quoted))
        self.assertEqual(result.discount_pct, Decimal(0))

    def test_discount_tiers(self):
        settings.configure(discount_tiers="2:1,5:3")
        result = run_batch(write_temp(self, SMALL_BATCH, ".csv"))
        self.assertEqual(result.discount_pct, Decimal(3))
        self.assertEqual(result.discount, (result.net_total * Decimal("0.03")).quantize(Decimal("0.01")))

    def test_bad_tiers_are_reported_when_used(self):
        settings.configure(discount_tiers="2-1")
        with self.assertRaises(SettingsError):
            run_batch(write_temp(self, SMALL_BATCH, ".csv"))

    def test_missing_column(self):
        with self.assertRaisesRegex(InputError, "missing column"):
            run_batch(write_temp(self, MISSING_COLUMN, ".csv"))

    def test_missing_file(self):
        with self.assertRaisesRegex(InputError, "cannot read"):
            run_batch("/nonexistent/batch.csv")


if __name__ == "__main__":
    unittest.main()
