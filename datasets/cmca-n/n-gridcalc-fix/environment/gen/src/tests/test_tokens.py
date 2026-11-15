import unittest

from gridcalc.errors import FormulaError
from gridcalc.tokens import tokenize


def kinds(text):
    return [(t.kind, t.text) for t in tokenize(text)]


class TokenTest(unittest.TestCase):
    # formulas.md 2.1
    def test_numbers(self):
        for text in ("12", "12.", ".5", "1.25", "1.5e3", "2E-2", "7e+1", "0.000"):
            with self.subTest(text=text):
                self.assertEqual(kinds(text), [("num", text)])

    def test_sign_is_an_operator(self):
        self.assertEqual(kinds("-4"), [("op", "-"), ("num", "4")])
        self.assertEqual(kinds("2e-3-1"), [("num", "2e-3"), ("op", "-"), ("num", "1")])

    # formulas.md 2.2
    def test_strings(self):
        self.assertEqual(kinds('"say ""hi"""'), [("str", 'say "hi"')])
        self.assertEqual(kinds('"a b"&"c"'), [("str", "a b"), ("op", "&"), ("str", "c")])
        self.assertEqual(kinds('""'), [("str", "")])

    def test_unterminated_string(self):
        with self.assertRaises(FormulaError):
            tokenize('"abc')

    # formulas.md 2.3, 2.4
    def test_references_and_names(self):
        self.assertEqual(kinds("$A$1+b2"), [("ref", "$A$1"), ("op", "+"), ("ref", "b2")])
        self.assertEqual(kinds("SUM(A1:B2)"), [("name", "SUM"), ("op", "("), ("ref", "A1"), ("op", ":"), ("ref", "B2"), ("op", ")")])
        self.assertEqual(kinds("LOG10(1)")[0], ("name", "LOG10"))
        self.assertEqual(kinds("A1B"), [("name", "A1B")])
        self.assertEqual(kinds("TRUE"), [("name", "TRUE")])

    # formulas.md 2.5
    def test_operators(self):
        self.assertEqual(kinds("1<=2"), [("num", "1"), ("op", "<="), ("num", "2")])
        self.assertEqual(kinds("1<>2"), [("num", "1"), ("op", "<>"), ("num", "2")])
        self.assertEqual(kinds("1< =2"), [("num", "1"), ("op", "<"), ("op", "="), ("num", "2")])
        self.assertEqual(kinds("50%"), [("num", "50"), ("op", "%")])

    def test_bad_characters(self):
        for text in ("1 ! 2", "A1 # 2", "."):
            with self.subTest(text=text):
                with self.assertRaises(FormulaError):
                    tokenize(text)
