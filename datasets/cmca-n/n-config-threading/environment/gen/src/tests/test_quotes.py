import unittest
from datetime import date
from decimal import Decimal

from quoter import settings
from quoter.core.errors import QuoteError
from quoter.services import cache
from quoter.services.quotes import cheapest, make_request, quote_all
from tests.helpers import SettingsCase


def berlin_paris():
    return make_request("DE-10115", "FR-75001", "2", "30x20x10")


class RequestTest(SettingsCase):
    def test_parses_addresses_and_dims(self):
        req = make_request("de-10115", "nl-1012ab", "1.5", "10x30x20", True, "99")
        self.assertEqual(str(req.dest), "NL-1012AB")
        self.assertEqual(req.dims, (Decimal(30), Decimal(20), Decimal(10)))
        self.assertEqual(req.weight, Decimal("1.5"))
        self.assertTrue(req.residential)
        self.assertEqual(req.declared, Decimal(99))

    def test_rejects_bad_input(self):
        for args in (("DE-10115", "FR-75001", "0"), ("DE-10115", "FR-75001", "2", "30x20"), ("DE-10115", "XX-1", "2"), ("DE-10115", "GB-12345", "2"), ("DE-10115", "FR-75001", "2", None, False, "-1")):
            with self.assertRaises(QuoteError):
                make_request(*args)


class QuoteTest(SettingsCase):
    def test_fallback_prices(self):
        quotes = quote_all(berlin_paris())
        self.assertEqual([(q.carrier, q.service) for q in quotes], [("ground", "eco"), ("ground", "std"), ("express", "2day"), ("express", "next"), ("express", "noon")])
        first = quotes[0]
        self.assertEqual((first.zone, first.box, first.chargeable_kg), (3, "M1", Decimal("4.8")))
        self.assertEqual((first.base, first.fuel, first.net, first.gross), (Decimal("12.33"), Decimal("1.23"), Decimal("13.56"), Decimal("16.27")))
        self.assertEqual(first.delivery, date(2026, 1, 12))

    def test_sorted_by_gross(self):
        gross = [q.gross for q in quote_all(berlin_paris())]
        self.assertEqual(gross, sorted(gross))

    def test_markup(self):
        express = quote_all(berlin_paris(), "express", "next")[0]
        self.assertEqual(express.markup, Decimal("1.01"))
        settings.configure(express_markup="10")
        self.assertEqual(quote_all(berlin_paris(), "express", "next")[0].markup, Decimal("2.54"))

    def test_rate_card(self):
        settings.configure(rate_card="2026")
        self.assertEqual([str(q.net) for q in quote_all(berlin_paris())], ["14.21", "15.79", "24.89", "31.75", "41.19"])

    def test_rounding_step(self):
        settings.configure(round_step="0.05", rounding="up")
        nets = [q.net for q in quote_all(berlin_paris())]
        self.assertEqual([str(n) for n in nets], ["13.60", "15.10", "23.80", "30.35", "39.35"])

    def test_currency(self):
        settings.configure(currency="USD")
        q = quote_all(berlin_paris())[0]
        self.assertEqual((q.currency, q.gross, q.gross_local), ("USD", Decimal("16.27"), Decimal("17.88")))

    def test_no_tax_outside_vat(self):
        req = make_request("GB-EC1A 1BB", "US-10001", "3.5")
        self.assertTrue(all(q.tax == 0 for q in quote_all(req)))

    def test_remote_residential_and_insurance(self):
        req = make_request("DE-10115", "DE-18565", "1", None, True, "1000")
        q = quote_all(req, "courier", "same")[0]
        self.assertEqual(q.surcharges, ("remote", "residential"))
        self.assertEqual(q.insurance, Decimal("12.00"))
        self.assertEqual(q.net, Decimal("41.18"))

    def test_peak_and_saturday(self):
        req = make_request("DE-10115", "DE-18565", "1", None, True, "1000")
        settings.configure(pricing_date="2026-12-01", surcharge_peak="2")
        q = quote_all(req, "ground", "eco")[0]
        self.assertEqual(q.surcharges, ("remote", "residential", "peak"))
        self.assertEqual(q.delivery, date(2026, 12, 8))
        settings.configure(saturday_delivery=True)
        self.assertEqual(quote_all(req, "ground", "eco")[0].delivery, date(2026, 12, 7))

    def test_box_sets(self):
        settings.configure(box_set="eco")
        self.assertEqual(quote_all(berlin_paris())[0].box, "E2")
        settings.configure(box_set="none")
        q = quote_all(berlin_paris())[0]
        self.assertIsNone(q.box)
        self.assertEqual(q.chargeable_kg, Decimal("2.0"))

    def test_carrier_order_breaks_ties(self):
        settings.configure(carriers="express")
        self.assertEqual({q.carrier for q in quote_all(berlin_paris())}, {"express"})
        with self.assertRaisesRegex(QuoteError, "not enabled"):
            quote_all(berlin_paris(), "ground")

    def test_courier_same_country_only(self):
        self.assertEqual(quote_all(berlin_paris(), "courier"), [])
        local = make_request("DE-10115", "DE-10117", "3", "20x20x20")
        self.assertEqual({q.service for q in quote_all(local, "courier")}, {"same", "eve"})

    def test_cheapest(self):
        self.assertEqual(cheapest(berlin_paris()).service, "eco")
        self.assertIsNone(cheapest(make_request("DE-10115", "US-10001", "900")))


class CacheTest(SettingsCase):
    def test_results_are_reused(self):
        settings.configure(cache_enabled=True)
        entries, hits = cache.stats()
        req = make_request("DE-10115", "AT-1010", "4.4", "33x21x17")
        first = quote_all(req)
        again = quote_all(req)
        self.assertEqual(first, again)
        new_entries, new_hits = cache.stats()
        self.assertEqual(new_entries - entries, 8)
        self.assertEqual(new_hits - hits, 8)

    def test_off_means_off(self):
        entries, hits = cache.stats()
        req = make_request("DE-10115", "AT-1010", "5.5", "33x21x18")
        quote_all(req)
        quote_all(req)
        self.assertEqual(cache.stats(), (entries, hits))


if __name__ == "__main__":
    unittest.main()
