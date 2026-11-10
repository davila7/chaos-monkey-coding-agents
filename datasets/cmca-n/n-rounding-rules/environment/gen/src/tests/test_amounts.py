"""Amounts computed by the library."""

import unittest
from datetime import date
from decimal import Decimal

from meterbill import cash, credits, standing, tariffs, tax
from meterbill.model import Credit, Segment


def D(s: str) -> Decimal:
    return Decimal(s)


class Bands(unittest.TestCase):
    def setUp(self):
        self.book = tariffs.load_book()

    def test_split_over_three_bands(self):
        got = tariffs.charge_bands(D("412.6"), self.book.tariff("home-2"))
        self.assertEqual([c.label for c in got], ["0 - 100", "100 - 300", "over 300"])
        self.assertEqual([c.kwh for c in got], [D("100"), D("200"), D("112.6")])
        self.assertEqual([c.amount for c in got], [D("20.10"), D("47.00"), D("31.42")])

    def test_within_first_band(self):
        got = tariffs.charge_bands(D("80.4"), self.book.tariff("home-1"))
        self.assertEqual([(c.label, c.amount) for c in got], [("0 - 150", D("17.21"))])

    def test_nothing_used(self):
        got = tariffs.charge_bands(D("0"), self.book.tariff("uk-std"))
        self.assertEqual(got, [])
        self.assertEqual(str(tariffs.energy_total(got)), "0.00")


class Standing(unittest.TestCase):
    def test_parts_add_up_to_the_rounded_whole(self):
        segs = [Segment(date(2026, 3, 1), date(2026, 3, 13), D("0.4113")), Segment(date(2026, 3, 14), date(2026, 3, 31), D("0.4387"))]
        parts = standing.prorate(segs)
        self.assertEqual(parts, [D("5.34"), D("7.90")])
        self.assertEqual(sum(parts), (13 * D("0.4113") + 18 * D("0.4387")).quantize(D("0.01")))

    def test_one_segment(self):
        self.assertEqual(standing.prorate([Segment(date(2026, 4, 1), date(2026, 4, 30), D("0.3890"))]), [D("11.67")])


class Tax(unittest.TestCase):
    def test_half_to_even(self):
        self.assertEqual(tax.vat(D("10.25"), D("0.1")), D("1.02"))
        self.assertEqual(tax.vat(D("10.35"), D("0.1")), D("1.04"))

    def test_label(self):
        self.assertEqual(tax.rate_label(D("0.21")), "VAT 21%")


class Cash(unittest.TestCase):
    def test_five_centimes(self):
        self.assertEqual(cash.payable(D("12.33"), "0.05"), D("12.35"))
        self.assertEqual(cash.payable(D("12.32"), "0.05"), D("12.30"))

    def test_whole_krona(self):
        self.assertEqual(cash.payable(D("122.40"), "whole"), D("122"))
        self.assertEqual(cash.payable(D("122.61"), "whole"), D("123"))

    def test_none(self):
        self.assertEqual(cash.payable(D("9.99"), "none"), D("9.99"))


class Credits(unittest.TestCase):
    def test_settle(self):
        self.assertEqual(credits.settle(-4.25), -4.25)
        self.assertEqual(credits.settle(4.256), 4.26)

    def test_total(self):
        cs = [Credit("a", -4.25), Credit("b", -1.1), Credit("c", 0.3)]
        self.assertEqual(credits.total(cs), D("-5.05"))
        self.assertEqual(credits.total([]), D("0.00"))


if __name__ == "__main__":
    unittest.main()
