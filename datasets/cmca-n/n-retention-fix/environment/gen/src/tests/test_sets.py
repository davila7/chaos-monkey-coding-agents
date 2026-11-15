import unittest

from retain.errors import ListingError, SetError, ZoneError
from retain.sets import load_set

from tests.support import zones

BASE = {"prefix": "db", "zone": "utc", "now": "2026-06-10T12:00:00Z", "policy": {"daily": 7}, "files": ["db-20260610T030000Z.tar"]}


class SetFileTest(unittest.TestCase):
    def load(self, **changes):
        raw = dict(BASE, **changes)
        for k in [k for k, v in raw.items() if v is None]:
            del raw[k]
        return load_set("t-1", raw, zones())

    def test_valid(self):
        s = self.load(pins=["db-20260610T030000Z.tar"])
        self.assertEqual((s.prefix, s.zone.zid, s.policy.daily, s.policy.last), ("db", "utc", 7, 0))

    def test_set_errors(self):
        for changes in ({"prefix": "DB"}, {"prefix": "db-x"}, {"prefix": ""}, {"now": "2026-06-10 12:00:00Z"}, {"now": "2026-06-10T12:00:00+00:00"},
                        {"now": "2026-06-31T12:00:00Z"}, {"files": None}, {"policy": None}, {"files": "db.tar"}, {"pins": "x"},
                        {"policy": {"daily": True}}, {"policy": {"daily": -1}}, {"policy": {"daily": "7"}}, {"policy": {"daily": 7.0}},
                        {"policy": {"hourly": 1}}, {"policy": {}}, {"policy": {"last": 0, "daily": 0}}, {"extra": 1}):
            with self.subTest(changes=changes):
                with self.assertRaises(SetError):
                    self.load(**changes)

    def test_keeps_nothing_even_with_pins(self):
        with self.assertRaises(SetError):
            self.load(policy={"recent_hours": 0}, pins=["db-20260610T030000Z.tar"])

    def test_zone_errors(self):
        for zid in ("UTC", "south", "", 3):
            with self.subTest(zid=zid):
                with self.assertRaises(ZoneError):
                    self.load(zone=zid)

    def test_listed_twice(self):
        for files in (["db-20260610T030000Z.tar", "db-20260610T030000Z.tar"], ["notes.txt", "notes.txt"]):
            with self.subTest(files=files):
                with self.assertRaises(ListingError):
                    self.load(files=files)
