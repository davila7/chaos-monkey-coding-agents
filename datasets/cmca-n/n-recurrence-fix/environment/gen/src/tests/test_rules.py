"""Parsing rules and the local times they generate."""

import unittest
from datetime import date, datetime
from itertools import islice

from agenda.errors import RuleError
from agenda.rules.expand import occurrences
from agenda.rules.parse import parse
from agenda.zones import Zone

UTC = Zone("UTC Test", 0)
HORIZON = date(2040, 1, 1)


def times(rule: str, start: str, n: int = 50) -> list[str]:
    r = parse(rule)
    gen = occurrences(r, datetime.fromisoformat(start), UTC, HORIZON)
    if r.count is not None:
        gen = islice(gen, r.count)
    return [t.strftime("%Y-%m-%dT%H:%M") for t in islice(gen, n)]


class ParseTest(unittest.TestCase):
    def test_parts(self):
        r = parse("FREQ=MONTHLY;BYDAY=2TU,-1FR;INTERVAL=3;COUNT=7")
        self.assertEqual((r.freq, r.interval, r.count, r.byday), ("MONTHLY", 3, 7, ((2, 1), (-1, 4))))
        self.assertEqual(parse("FREQ=WEEKLY;WKST=SU").wkst, 6)
        self.assertEqual(parse("FREQ=DAILY;UNTIL=20270501").until, ("date", date(2027, 5, 1)))
        self.assertEqual(parse("FREQ=DAILY;UNTIL=20270501T153000Z").until, ("utc", datetime(2027, 5, 1, 15, 30)))
        self.assertEqual(parse("FREQ=MONTHLY;BYDAY=+1MO").byday, ((1, 0),))

    def test_errors(self):
        for text in ("", "FREQ=HOURLY", "FREQ=DAILY;FREQ=DAILY", "FREQ=DAILY;BYHOUR=9", "FREQ=DAILY;COUNT=3;UNTIL=20270101",
                     "FREQ=WEEKLY;BYMONTHDAY=3", "FREQ=WEEKLY;BYDAY=1MO", "FREQ=DAILY;BYDAY=-1FR", "FREQ=YEARLY;BYDAY=1MO",
                     "FREQ=MONTHLY;BYDAY=6MO", "FREQ=DAILY;BYSETPOS=1;BYDAY=MO", "FREQ=MONTHLY;BYSETPOS=1",
                     "FREQ=MONTHLY;BYMONTHDAY=0", "FREQ=MONTHLY;BYMONTHDAY=32", "FREQ=MONTHLY;BYMONTHDAY=1,1",
                     "FREQ=DAILY;INTERVAL=0", "FREQ=DAILY;COUNT=x", "FREQ=DAILY;UNTIL=2027-05-01", "FREQ=WEEKLY;WKST=XX",
                     "freq=daily", "FREQ=DAILY;"):
            with self.subTest(text=text), self.assertRaises(RuleError):
                parse(text)


class DailyWeeklyTest(unittest.TestCase):
    def test_daily_interval(self):
        self.assertEqual(times("FREQ=DAILY;INTERVAL=3;COUNT=4", "2027-02-25T09:00"),
                         ["2027-02-25T09:00", "2027-02-28T09:00", "2027-03-03T09:00", "2027-03-06T09:00"])

    def test_daily_limited_by_weekday(self):
        self.assertEqual(times("FREQ=DAILY;BYDAY=MO,FR;COUNT=4", "2027-05-05T08:00"),
                         ["2027-05-05T08:00", "2027-05-07T08:00", "2027-05-10T08:00", "2027-05-14T08:00"])

    def test_weekly_days(self):
        self.assertEqual(times("FREQ=WEEKLY;BYDAY=TU,TH;COUNT=5", "2027-06-01T10:00"),
                         ["2027-06-01T10:00", "2027-06-03T10:00", "2027-06-08T10:00", "2027-06-10T10:00", "2027-06-15T10:00"])

    def test_weekly_default_day(self):
        self.assertEqual(times("FREQ=WEEKLY;INTERVAL=2;COUNT=3", "2027-06-02T10:00"),
                         ["2027-06-02T10:00", "2027-06-16T10:00", "2027-06-30T10:00"])

    def test_start_off_the_rule(self):
        self.assertEqual(times("FREQ=WEEKLY;BYDAY=MO;COUNT=3", "2027-06-01T10:00"),
                         ["2027-06-01T10:00", "2027-06-07T10:00", "2027-06-14T10:00"])


class MonthlyYearlyTest(unittest.TestCase):
    def test_monthday_skips_short_months(self):
        self.assertEqual(times("FREQ=MONTHLY;BYMONTHDAY=31;COUNT=4", "2027-01-31T12:00"),
                         ["2027-01-31T12:00", "2027-03-31T12:00", "2027-05-31T12:00", "2027-07-31T12:00"])

    def test_default_day_skips_short_months(self):
        self.assertEqual(times("FREQ=MONTHLY;COUNT=3", "2027-08-31T12:00"),
                         ["2027-08-31T12:00", "2027-10-31T12:00", "2027-12-31T12:00"])

    def test_negative_monthday(self):
        self.assertEqual(times("FREQ=MONTHLY;BYMONTHDAY=-1;COUNT=3", "2028-01-31T07:00"),
                         ["2028-01-31T07:00", "2028-02-29T07:00", "2028-03-31T07:00"])

    def test_nth_weekday(self):
        self.assertEqual(times("FREQ=MONTHLY;BYDAY=2TU;COUNT=3", "2027-01-12T09:00"),
                         ["2027-01-12T09:00", "2027-02-09T09:00", "2027-03-09T09:00"])

    def test_last_weekday(self):
        self.assertEqual(times("FREQ=MONTHLY;BYDAY=-1FR;COUNT=4", "2027-01-29T16:00"),
                         ["2027-01-29T16:00", "2027-02-26T16:00", "2027-03-26T16:00", "2027-04-30T16:00"])

    def test_second_to_last_weekday(self):
        self.assertEqual(times("FREQ=MONTHLY;BYDAY=-2MO;COUNT=3", "2027-01-18T09:00"),
                         ["2027-01-18T09:00", "2027-02-15T09:00", "2027-03-22T09:00"])

    def test_fifth_weekday_only_where_it_exists(self):
        self.assertEqual(times("FREQ=MONTHLY;BYDAY=5MO;COUNT=3", "2027-03-29T09:00"),
                         ["2027-03-29T09:00", "2027-05-31T09:00", "2027-08-30T09:00"])

    def test_setpos_last_working_day(self):
        self.assertEqual(times("FREQ=MONTHLY;BYDAY=MO,TU,WE,TH,FR;BYSETPOS=-1;COUNT=4", "2027-01-29T17:00"),
                         ["2027-01-29T17:00", "2027-02-26T17:00", "2027-03-31T17:00", "2027-04-30T17:00"])

    def test_monthday_and_weekday(self):
        self.assertEqual(times("FREQ=MONTHLY;BYDAY=FR;BYMONTHDAY=13;COUNT=3", "2027-08-13T21:00"),
                         ["2027-08-13T21:00", "2028-10-13T21:00", "2029-04-13T21:00"])

    def test_leap_day(self):
        self.assertEqual(times("FREQ=YEARLY;COUNT=3", "2028-02-29T10:00"),
                         ["2028-02-29T10:00", "2032-02-29T10:00", "2036-02-29T10:00"])

    def test_yearly_nth(self):
        self.assertEqual(times("FREQ=YEARLY;BYMONTH=11;BYDAY=4TH;COUNT=3", "2027-11-25T15:00"),
                         ["2027-11-25T15:00", "2028-11-23T15:00", "2029-11-22T15:00"])

    def test_yearly_months(self):
        self.assertEqual(times("FREQ=YEARLY;BYMONTH=3,9;COUNT=4", "2027-03-10T09:00"),
                         ["2027-03-10T09:00", "2027-09-10T09:00", "2028-03-10T09:00", "2028-09-10T09:00"])


class EndTest(unittest.TestCase):
    def test_count(self):
        self.assertEqual(len(times("FREQ=DAILY;COUNT=12", "2027-01-01T09:00")), 12)
        self.assertEqual(times("FREQ=DAILY;COUNT=1", "2027-01-01T09:00"), ["2027-01-01T09:00"])

    def test_until_date_is_inclusive(self):
        self.assertEqual(times("FREQ=DAILY;UNTIL=20270104", "2027-01-01T23:30"),
                         ["2027-01-01T23:30", "2027-01-02T23:30", "2027-01-03T23:30", "2027-01-04T23:30"])
        self.assertEqual(times("FREQ=WEEKLY;UNTIL=20270115", "2027-01-01T09:00"),
                         ["2027-01-01T09:00", "2027-01-08T09:00", "2027-01-15T09:00"])

    def test_until_before_start(self):
        self.assertEqual(times("FREQ=DAILY;UNTIL=20261231", "2027-01-01T09:00"), ["2027-01-01T09:00"])

    def test_until_utc_in_utc_zone(self):
        self.assertEqual(times("FREQ=DAILY;UNTIL=20270103T090000Z", "2027-01-01T09:00"),
                         ["2027-01-01T09:00", "2027-01-02T09:00", "2027-01-03T09:00"])
