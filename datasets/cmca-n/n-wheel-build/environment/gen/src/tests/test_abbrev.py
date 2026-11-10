import unittest

import tests.support  # noqa: F401

from orbis.postal.abbrev import abbreviate, table
from orbis.postal.countries import countries, country_format


class AbbreviationTest(unittest.TestCase):
    def test_every_named_table_exists(self):
        for code in countries():
            name = country_format(code).abbreviations
            if name:
                with self.subTest(code=code):
                    self.assertEqual(table(name).name, name)

    def test_words(self):
        self.assertEqual(abbreviate("North Park Avenue", table("en")), "N Park Ave")
        self.assertEqual(abbreviate("Rue de la Gare", table("fr")), "r. de la Gare")
        self.assertEqual(abbreviate("Piazza Garibaldi", table("it")), "P.zza Garibaldi")

    def test_suffixes(self):
        self.assertEqual(abbreviate("Hauptstraße", table("de")), "Hauptstr.")
        self.assertEqual(abbreviate("Bahnhofstrasse", table("de")), "Bahnhofstr.")
        self.assertEqual(abbreviate("Prinsengracht", table("nl")), "Prinsengr.")
        self.assertEqual(abbreviate("Drottninggatan", table("sv")), "Drottningg.")

    def test_word_alone_is_not_a_suffix(self):
        self.assertEqual(abbreviate("Straat", table("nl")), "Str.")
        self.assertEqual(abbreviate("laan", table("nl")), "laan")

    def test_untouched(self):
        self.assertEqual(abbreviate("Gartenweg", table("de")), "Gartenweg")


if __name__ == "__main__":
    unittest.main()
