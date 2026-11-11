import unittest
from datetime import datetime

from retain.errors import ZoneError
from retain.names import iso
from retain.zones import load_zones, transition

from tests.support import at, zones


class TransitionTest(unittest.TestCase):
    def test_last_sunday(self):
        rule = {"month": 3, "week": "last", "weekday": 6, "minutes": 60}
        self.assertEqual(iso(transition(2026, rule)), "2026-03-29T01:00:00Z")
        self.assertEqual(iso(transition(2027, rule)), "2027-03-28T01:00:00Z")

    def test_nth_weekday(self):
        self.assertEqual(iso(transition(2026, {"month": 3, "week": 2, "weekday": 6, "minutes": 420})), "2026-03-08T07:00:00Z")
        self.assertEqual(iso(transition(2026, {"month": 11, "week": 1, "weekday": 6, "minutes": 360})), "2026-11-01T06:00:00Z")
        self.assertEqual(iso(transition(2026, {"month": 6, "week": 1, "weekday": 0, "minutes": 0})), "2026-06-01T00:00:00Z")


class OffsetTest(unittest.TestCase):
    def test_north(self):
        z = zones()["north"]
        for t, off in (("2026-03-29T00:59:59Z", 60), ("2026-03-29T01:00:00Z", 120), ("2026-07-01T00:00:00Z", 120),
                       ("2026-10-25T00:59:59Z", 120), ("2026-10-25T01:00:00Z", 60), ("2026-12-31T23:00:00Z", 60)):
            with self.subTest(t=t):
                self.assertEqual(z.offset(at(t)), off)

    def test_west(self):
        z = zones()["west"]
        self.assertEqual(z.offset(at("2026-03-08T06:59:00Z")), -300)
        self.assertEqual(z.offset(at("2026-03-08T07:00:00Z")), -240)
        self.assertEqual(z.offset(at("2026-11-01T06:00:00Z")), -300)

    def test_fixed(self):
        self.assertEqual(zones()["utc"].offset(at("2026-07-01T00:00:00Z")), 0)

    def test_to_local(self):
        z = zones()["north"]
        self.assertEqual(z.to_local(at("2026-07-01T22:30:00Z")).isoformat(), "2026-07-02T00:30:00")


class WallTimeTest(unittest.TestCase):
    # zones.md 4.4
    def test_table(self):
        z = zones()["north"]
        for wall, want in (("2026-03-29T00:59:00", "2026-03-28T23:59:00Z"), ("2026-03-29T02:30:00", "2026-03-29T01:30:00Z"),
                           ("2026-03-29T03:00:00", "2026-03-29T01:00:00Z"), ("2026-10-25T02:30:00", "2026-10-25T00:30:00Z"),
                           ("2026-10-25T03:00:00", "2026-10-25T02:00:00Z")):
            with self.subTest(wall=wall):
                self.assertEqual(iso(z.from_local(datetime.fromisoformat(wall))), want)

    def test_occurs_twice_west(self):
        z = zones()["west"]
        self.assertEqual(iso(z.from_local(datetime(2026, 11, 1, 1, 30))), "2026-11-01T05:30:00Z")

    def test_round_trip(self):
        z = zones()["west"]
        for t in ("2026-01-15T12:00:00Z", "2026-03-08T07:00:00Z", "2026-07-04T03:00:00Z", "2026-11-01T07:00:00Z"):
            with self.subTest(t=t):
                self.assertEqual(iso(z.from_local(z.to_local(at(t)))), t)


class TableTest(unittest.TestCase):
    def test_errors(self):
        rule = {"month": 3, "week": "last", "weekday": 6, "at": "01:00"}
        for raw in ({}, {"x": {"dst": 60}}, {"x": {"std": 60, "dst": 120}}, {"x": {"std": 60, "dst": 30, "start": rule, "end": dict(rule, month=10)}},
                    {"x": {"std": 60, "dst": 120, "start": rule, "end": rule}}, {"x": {"std": 900}}, {"x": {"std": 60.0}},
                    {"x": {"std": 60, "dst": 120, "start": dict(rule, week=5), "end": dict(rule, month=10)}},
                    {"x": {"std": 60, "dst": 120, "start": dict(rule, at="1:00"), "end": dict(rule, month=10)}},
                    {"x": {"std": 0, "name": "x"}}):
            with self.subTest(raw=raw):
                with self.assertRaises(ZoneError):
                    load_zones(raw)
