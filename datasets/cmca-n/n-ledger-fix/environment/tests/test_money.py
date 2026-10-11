import unittest

from ledger.money import format_cents, parse_amount


class MoneyTest(unittest.TestCase):
    def test_whole_and_two_decimals(self):
        self.assertEqual(parse_amount("980"), 98000)
        self.assertEqual(parse_amount("12.05"), 1205)

    def test_one_decimal(self):
        self.assertEqual(parse_amount("2450.5"), 245050)

    def test_accounting_negative(self):
        self.assertEqual(parse_amount("(3.40)"), -340)

    def test_format(self):
        self.assertEqual(format_cents(-340), "-3.40")
        self.assertEqual(format_cents(245050), "2450.50")


if __name__ == "__main__":
    unittest.main()
