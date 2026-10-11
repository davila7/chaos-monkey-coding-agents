import unittest

from ledger.convert import round_cents, to_base
from ledger.money import Money


class ConvertTest(unittest.TestCase):
    def test_base_currency_is_unchanged(self):
        self.assertEqual(round_cents(to_base(Money(1234, "USD"), "1")), 1234)

    def test_plain_conversion(self):
        self.assertEqual(round_cents(to_base(Money(-8730, "EUR"), "1.0790")), -9420)

    def test_half_cent(self):
        self.assertEqual(round_cents(to_base(Money(1500, "EUR"), "1.0790")), 1619)

    def test_exact_decimal_product(self):
        self.assertEqual(round_cents(to_base(Money(5000, "EUR"), "1.0835")), 5418)
        self.assertEqual(Money(2500, "GBP").in_base("1.2710"), 3178)


if __name__ == "__main__":
    unittest.main()
