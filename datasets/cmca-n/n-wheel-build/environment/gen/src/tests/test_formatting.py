import unittest

from tests.support import FIXTURES, expected

from orbis.postal import Address, AddressError, format_address
from orbis.postal.countries import countries, country_format, regions
from orbis.postal.records import read_records


def addr(**kw):
    kw.setdefault("id", "t1")
    return Address.from_mapping(kw, 1)


class CountryDataTest(unittest.TestCase):
    def test_every_indexed_country_has_a_format(self):
        for code in countries():
            with self.subTest(code=code):
                self.assertEqual(country_format(code).code, code)

    def test_regions(self):
        self.assertEqual(regions(), ["africa", "americas", "asia", "europe", "oceania"])

    def test_index_size(self):
        self.assertEqual(len(countries()), 30)


class FormatTest(unittest.TestCase):
    def test_german_order_without_country_line_at_home(self):
        a = addr(country="DE", recipient="Anna Müller", organisation="Acme GmbH", street="Hauptstraße", number="5", postcode="10115", city="Berlin")
        self.assertEqual(format_address(a, origin="de"), ["Acme GmbH", "Anna Müller", "Hauptstraße 5", "10115 Berlin"])

    def test_country_line_abroad(self):
        a = addr(country="FR", recipient="Jean Dupont", street="Rue de la Gare", number="12", postcode="75001", city="Paris")
        self.assertEqual(format_address(a, origin="DE")[-2:], ["75001 PARIS", "FRANCE"])

    def test_us_abbreviates_by_default(self):
        a = addr(country="us", recipient="Olivia Smith", street="Main Street", number="12", postcode="62701", city="Springfield", region="il")
        self.assertEqual(format_address(a), ["Olivia Smith", "12 Main St", "SPRINGFIELD, IL 62701", "UNITED STATES"])

    def test_abbreviation_can_be_turned_off_and_on(self):
        us = addr(country="US", street="Oak Avenue", number="3", postcode="97201", city="Portland", region="OR")
        self.assertEqual(format_address(us, abbreviate=False)[0], "3 Oak Avenue")
        de = addr(country="DE", street="Lindenstraße", number="1", postcode="50667", city="Köln")
        self.assertEqual(format_address(de, abbreviate=True)[0], "Lindenstr. 1")

    def test_empty_fields_leave_no_separators(self):
        a = addr(country="ES", recipient="María Núñez", street="Calle Mayor", postcode="28013", city="Madrid")
        self.assertEqual(format_address(a, origin="ES"), ["María Núñez", "Calle Mayor", "28013 Madrid"])

    def test_postcode_layout(self):
        a = addr(country="NL", street="Kerkstraat", number="9", postcode="1017 gc", city="Amsterdam")
        self.assertIn("1017 GC AMSTERDAM", format_address(a))

    def test_invalid_postcode(self):
        a = addr(country="GB", street="High Street", number="1", postcode="12345", city="Leeds")
        with self.assertRaises(AddressError):
            format_address(a)

    def test_unknown_country(self):
        with self.assertRaises(AddressError):
            format_address(addr(country="ZZ", city="Nowhere"))

    def test_fixture_text(self):
        out = []
        for a in read_records(FIXTURES / "addresses.jsonl"):
            out.append("\n".join(format_address(a)))
        self.assertEqual("\n\n".join(out) + "\n", expected("text.txt"))


if __name__ == "__main__":
    unittest.main()
