"""Quantities, conversion to SI units and expressing a result in a target unit."""

import unittest
from fractions import Fraction as F

from measure.convert import express, from_si
from measure.errors import DimensionError, ParseError

from tests.support import quantity, unit


class QuantityTest(unittest.TestCase):
    def test_parts(self):
        q = quantity("  3.20 km/h ")
        self.assertEqual((q.value, q.sig_figs, q.unit.text), (F("3.2"), 3, "km/h"))
        self.assertEqual(q.si(), F(32, 36))

    def test_dimensionless(self):
        self.assertEqual(quantity("0.25").si(), F(1, 4))
        self.assertEqual(quantity("0.25").dim, quantity("0.25 1").dim)
        self.assertEqual(quantity("12.5 percent").si(), F(1, 8))

    def test_several_spaces(self):
        self.assertEqual(quantity("4   m").si(), 4)

    def test_refused(self):
        for text in ("m", "", "3,5 m", "2 m s", "1.5 m/ s"):
            with self.subTest(text=text):
                with self.assertRaises(ParseError):
                    quantity(text)


class ToSiTest(unittest.TestCase):
    def test_linear(self):
        cases = {"1 mi": F("1609.344"), "1 lb": F("0.45359237"), "2.5 h": 9000, "3 L": F(3, 1000),
                 "1 bar": 100000, "250 mbar": 25000, "1 kcal": 4184, "40 percent": F(2, 5)}
        for text, si in cases.items():
            with self.subTest(text=text):
                self.assertEqual(quantity(text).si(), si)

    def test_absolute_temperatures(self):
        self.assertEqual(quantity("100 degC").si(), F("373.15"))
        self.assertEqual(quantity("212 degF").si(), F("373.15"))
        self.assertEqual(quantity("32 degF").si(), F("273.15"))
        self.assertEqual(quantity("-40 degF").si(), quantity("-40 degC").si())
        self.assertEqual(quantity("491.67 degR").si(), F("273.15"))

    def test_differences(self):
        self.assertEqual(quantity("9 delta_degF").si(), 5)
        self.assertEqual(quantity("5 delta_degC").si(), 5)
        self.assertEqual(quantity("5 K").si(), 5)


class ExpressTest(unittest.TestCase):
    def test_absolute(self):
        si = quantity("98.6 degF").si()
        self.assertEqual(express(si, "absolute", unit("K").dim, unit("degC")), 37)
        self.assertEqual(express(F("373.15"), "absolute", unit("K").dim, unit("degF")), 212)
        self.assertEqual(express(F("373.15"), "absolute", unit("K").dim, unit("K")), F("373.15"))

    def test_plain_temperature(self):
        self.assertEqual(express(F(300), "plain", unit("K").dim, unit("degC")), F("26.85"))
        self.assertEqual(express(F(5), "plain", unit("K").dim, unit("delta_degF")), 9)

    def test_difference(self):
        self.assertEqual(express(F(5), "difference", unit("K").dim, unit("delta_degF")), 9)
        self.assertEqual(express(F(5), "difference", unit("K").dim, unit("degR")), 9)
        self.assertEqual(express(F(5), "difference", unit("K").dim, unit("K")), 5)

    def test_refused(self):
        temp = unit("K").dim
        with self.assertRaises(DimensionError):
            express(F(5), "difference", temp, unit("degC"))
        with self.assertRaises(DimensionError):
            express(F(300), "absolute", temp, unit("delta_degC"))
        with self.assertRaises(DimensionError):
            express(F(300), "plain", temp, unit("m"))
        with self.assertRaises(DimensionError):
            express(F(1), "plain", unit("kg").dim, unit("N"))

    def test_linear(self):
        self.assertEqual(express(F(1000), "plain", unit("m").dim, unit("km")), 1)
        self.assertEqual(express(F(1), "plain", unit("m/s").dim, unit("km/h")), F("3.6"))
        self.assertEqual(express(F("0.3048"), "plain", unit("m").dim, unit("ft")), 1)
        self.assertEqual(from_si(F(1), unit("percent")), 100)
