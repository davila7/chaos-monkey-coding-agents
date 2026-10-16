import unittest

from tests.support import run


class ReportTest(unittest.TestCase):
    def test_text(self):
        lines = run("report", "orders", "--by", "status", "--sum", "total").text.splitlines()
        self.assertEqual(lines[-1].split(), ["total", "5", "2910.74"])

    def test_csv_with_locale(self):
        r = run("report", "orders", "--by", "status", "--sum", "total", "--locale", "de-DE", "--format", "csv")
        self.assertEqual(r.text.splitlines()[1], 'open,3,"2.930,75"')

    def test_sum_needs_number(self):
        self.assertEqual(run("report", "orders", "--by", "status", "--sum", "customer").status, 2)


class StatsTest(unittest.TestCase):
    def test_sum(self):
        line = next(x for x in run("stats", "orders").text.splitlines() if x.startswith("total "))
        self.assertTrue(line.rstrip().endswith("2910.74"))


class ValidateTest(unittest.TestCase):
    def test_fixture_store_is_valid(self):
        r = run("validate")
        self.assertEqual(r.status, 0)
        self.assertIn("0 problems", r.text)


if __name__ == "__main__":
    unittest.main()
