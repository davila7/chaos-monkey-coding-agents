import unittest

from retain.names import iso, parse_name, stamp_offset

from tests.support import zones


class StampTest(unittest.TestCase):
    def setUp(self):
        self.utc = zones()["utc"]
        self.north = zones()["north"]

    def when(self, name, zone=None, prefix="db"):
        b = parse_name(name, prefix, zone or self.utc)
        return None if b is None else iso(b.at)

    def test_utc(self):
        self.assertEqual(self.when("db-20260412T031500Z.tar.gz"), "2026-04-12T03:15:00Z")
        self.assertEqual(self.when("db-20260412T031500Z.tar.gz", self.north), "2026-04-12T03:15:00Z")

    def test_positive_offset(self):
        self.assertEqual(self.when("db-20260412T051500+0200.dump"), "2026-04-12T03:15:00Z")
        self.assertEqual(self.when("db-20260412T084500+0530.dump"), "2026-04-12T03:15:00Z")

    def test_negative_offset(self):
        self.assertEqual(self.when("db-20260411T231500-0400.dump"), "2026-04-12T03:15:00Z")
        self.assertEqual(self.when("db-20260411T224500-0430.dump"), "2026-04-12T03:15:00Z")

    def test_zero_offsets(self):
        for name in ("db-20260412T031500+0000.tar", "db-20260412T031500-0000.tar"):
            with self.subTest(name=name):
                self.assertEqual(self.when(name), "2026-04-12T03:15:00Z")

    def test_offset_values(self):
        for text, minutes in (("+0200", 120), ("-0400", -240), ("+0545", 345), ("-0930", -570), ("+1400", 840), ("-1400", -840)):
            with self.subTest(text=text):
                self.assertEqual(stamp_offset(text), minutes)
        for text in ("+1500", "-0060", "+0099"):
            with self.subTest(text=text):
                self.assertIsNone(stamp_offset(text))

    def test_local(self):
        self.assertEqual(self.when("db-20260412T051500.tar", self.north), "2026-04-12T03:15:00Z")
        self.assertEqual(self.when("db-20260112T051500.tar", self.north), "2026-01-12T04:15:00Z")

    def test_local_wall_time_of_the_set(self):
        b = parse_name("db-20260412T031500Z.tar", "db", self.north)
        self.assertEqual(b.local.isoformat(), "2026-04-12T05:15:00")

    def test_extensions(self):
        for name in ("db-20260412T031500Z.tar", "db-20260412T031500Z.tar.gz", "db-20260412T031500Z.log.1", "db-20260412T031500Z.sql.zst"):
            with self.subTest(name=name):
                self.assertEqual(self.when(name), "2026-04-12T03:15:00Z")


class ForeignTest(unittest.TestCase):
    def test_not_backups(self):
        utc = zones()["utc"]
        for name in ("db2-20260412T031500Z.tar", "dbx-20260412T031500Z.tar", "xdb-20260412T031500Z.tar", "README", "db-latest.tar",
                     "db-20260412T031500Z", "db_20260412T031500Z.tar", "db-20260231T031500Z.tar", "db-20260412T246000Z.tar",
                     "db-20260412T031500+1500.tar", "db-20260412.tar", "db-20260412T031500z.tar", "db-20260412T031500Z.TAR",
                     "DB-20260412T031500Z.tar", "db--20260412T031500Z.tar", " db-20260412T031500Z.tar", "db-20260412T031500Z.tar "):
            with self.subTest(name=name):
                self.assertIsNone(parse_name(name, "db", utc))
