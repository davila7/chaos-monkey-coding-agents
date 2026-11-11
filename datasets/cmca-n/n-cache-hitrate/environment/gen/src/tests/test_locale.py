import unittest

from shelfmark import locale

SUPPORTED = ("en", "es", "fr", "pt-BR")


def pick(header):
    return locale.negotiate(header, SUPPORTED, "en")


class Ranges(unittest.TestCase):
    def test_order(self):
        self.assertEqual(locale.ranges("fr;q=0.5, es, de;q=0.9"), ["es", "de", "fr"])

    def test_equal_weights_keep_order(self):
        self.assertEqual(locale.ranges("de;q=0.5,fr;q=0.5"), ["de", "fr"])

    def test_dropped(self):
        self.assertEqual(locale.ranges("es;q=0, fr;q=abc, en"), ["en"])

    def test_empty(self):
        self.assertEqual(locale.ranges(""), [])


class Negotiate(unittest.TestCase):
    def test_exact(self):
        self.assertEqual(pick("es"), "es")
        self.assertEqual(pick("PT-br"), "pt-BR")

    def test_weights_decide(self):
        self.assertEqual(pick("fr;q=0.2, es;q=0.8"), "es")

    def test_star_and_none(self):
        self.assertEqual(pick("*"), "en")
        self.assertEqual(pick(None), "en")
        self.assertEqual(pick("ja, ko"), "en")

    def test_unsupported_then_supported(self):
        self.assertEqual(pick("it, fr;q=0.5"), "fr")


if __name__ == "__main__":
    unittest.main()
