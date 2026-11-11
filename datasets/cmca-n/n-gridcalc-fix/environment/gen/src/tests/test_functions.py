import unittest

from tests.support import formula, values

BLOCK = {"A1": "3", "A2": "apple", "A3": "TRUE", "A4": "5", "B1": "2.5", "B2": "-1", "B4": "'pear"}


class AggregateTest(unittest.TestCase):
    # functions.md 2
    def test_ranges(self):
        for expr, want in (("SUM(A1:A4)", 8), ("SUM(A1:B4)", 9.5), ("AVERAGE(A1:A4)", 4), ("MIN(A1:B4)", -1), ("MAX(A1:B4)", 5),
                           ("SUM(A2:A3)", 0), ("MIN(A2:A3)", 0), ("SUM((A1:A4))", 8), ("sum(a1:a4)", 8)):
            with self.subTest(expr=expr):
                self.assertEqual(formula(expr, BLOCK), want)

    def test_expression_arguments(self):
        for expr, want in (('SUM(A1, "4")', 7), ("SUM(TRUE, 2)", 3), ('SUM("x", 1)', "#VALUE!"), ("SUM(A1+0, B1*2)", 8),
                           ("AVERAGE(A1, 6)", 4.5), ("MAX(-3, -7)", -3)):
            with self.subTest(expr=expr):
                self.assertEqual(formula(expr, BLOCK), want)

    def test_no_numbers(self):
        self.assertEqual(formula("AVERAGE(A2:A3)", BLOCK), "#DIV/0!")
        self.assertEqual(formula("MAX(A2)", BLOCK), 0)

    def test_errors_in_ranges(self):
        cells = dict(BLOCK, A5="=1/0")
        self.assertEqual(formula("SUM(A1:A5)", cells), "#DIV/0!")
        self.assertEqual(formula("COUNT(A1:A5)", cells), 2)

    # functions.md 3
    def test_count(self):
        self.assertEqual(formula("COUNT(A1:B4)", BLOCK), 4)
        self.assertEqual(formula('COUNT(2, TRUE, "7", "x")', BLOCK), 3)
        self.assertEqual(formula("COUNT(1/0, 1)", BLOCK), 1)


class RoundTest(unittest.TestCase):
    # functions.md 4
    def test_round(self):
        for expr, want in (("ROUND(2.5)", 3), ("ROUND(-2.5)", -3), ("ROUND(2.675, 2)", 2.68), ("ROUND(1234, -2)", 1200),
                           ("ROUND(1.25, 1)", 1.3), ("ROUND(7.77, 1.9)", 7.8), ("ROUND(1, 11)", "#VALUE!"), ("ABS(-4)", 4), ("ABS(A1-A4)", 2)):
            with self.subTest(expr=expr):
                self.assertEqual(formula(expr, BLOCK), want)


class TextTest(unittest.TestCase):
    # functions.md 5
    def test_concat(self):
        self.assertEqual(formula('CONCAT("id-", A1, "/", A2)', BLOCK), "id-3/apple")
        self.assertEqual(formula("CONCAT(A1:B2)", BLOCK), "3apple2.5-1")
        self.assertEqual(formula("CONCAT(A1:A4)", BLOCK), "3appleTRUE5")
        self.assertEqual(formula("CONCAT(A1:A2, B1)", BLOCK), "3apple2.5")
        self.assertEqual(formula('LEN("abc")', BLOCK), 3)
        self.assertEqual(formula("LEN(A2)", BLOCK), 5)


class LogicTest(unittest.TestCase):
    # functions.md 6
    def test_and_or_not(self):
        for expr, want in (("AND(A1>0, A4>A1)", True), ("AND(A1:A4)", True), ("OR(FALSE, 0)", False), ("NOT(A3)", False),
                           ('AND("yes")', "#VALUE!"), ("OR(A2)", "#VALUE!"), ("NOT(0)", True)):
            with self.subTest(expr=expr):
                self.assertEqual(formula(expr, BLOCK), want)

    def test_if(self):
        for expr, want in (("IF(A1>2, A1, A4)", 3), ('IF(A1>4, "big", "small")', "small"), ("IF(FALSE, 1)", False),
                           ('IF("true", 1, 2)', 1), ('IF("maybe", 1, 2)', "#VALUE!"), ("IF(A3, B1, B2)", 2.5)):
            with self.subTest(expr=expr):
                self.assertEqual(formula(expr, BLOCK), want)

    def test_iferror(self):
        self.assertEqual(formula("IFERROR(1/0, 7)", BLOCK), 7)
        self.assertEqual(formula("IFERROR(A1, 1/0)", BLOCK), 3)
        self.assertEqual(formula('IFERROR(A2+1, "n/a")', BLOCK), "n/a")


class CallTest(unittest.TestCase):
    # functions.md 1.1, 1.3
    def test_calls(self):
        self.assertEqual(formula("SUMM(A1)", BLOCK), "#NAME?")
        self.assertEqual(formula("ABS(1, 2)", BLOCK), "#VALUE!")
        self.assertEqual(formula("IF(TRUE)", BLOCK), "#VALUE!")
        self.assertEqual(formula("ROUND(1/0, 2)", BLOCK), "#DIV/0!")
        self.assertEqual(formula("SUM(1/0, FOO)", BLOCK), "#DIV/0!")
        self.assertEqual(formula("ABS(A1:A2)", BLOCK), "#VALUE!")


class ErrorTest(unittest.TestCase):
    # values.md 5
    def test_errors(self):
        for expr, want in (("1/0", "#DIV/0!"), ("0^-1", "#DIV/0!"), ("ZZZ1*2", "#REF!"), ("SUM(A1:AAA2)", "#REF!"), ("A1:B2+1", "#VALUE!"),
                           ("(-8)^0.5", "#NUM!"), ("10^400", "#NUM!"), ("(1/0)+FOO", "#DIV/0!"), ("FOO+(1/0)", "#NAME?"),
                           ("1/0=1", "#DIV/0!"), ('"a"&(1/0)', "#DIV/0!"), ("0^0", 1)):
            with self.subTest(expr=expr):
                self.assertEqual(formula(expr, BLOCK), want)

    # values.md 6
    def test_cycles(self):
        v = values("A1: =B1+1\nB1: =A1*2\nC1: =A1+1\nC2: =IFERROR(A1, 0)\nD1: =D1\nD2: 4\n")
        self.assertEqual(v, {"A1": "#CYCLE!", "B1": "#CYCLE!", "C1": "#CYCLE!", "C2": 0, "D1": "#CYCLE!", "D2": 4})
