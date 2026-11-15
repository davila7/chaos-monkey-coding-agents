"""Each source's own reading of its times."""

import unittest
from datetime import date, datetime, timedelta, timezone

from deskstats import calls, chats, closures, escalations, roster, site, tickets

PLUS1 = timezone(timedelta(hours=1))


class Sources(unittest.TestCase):
    def test_site_offset(self):
        self.assertEqual(site.parse_offset("+01:00"), PLUS1)
        self.assertEqual(site.parse_offset("-05:00").utcoffset(None), timedelta(hours=-5))
        with self.assertRaises(ValueError):
            site.parse_offset("+0100")

    def test_ticket_times(self):
        self.assertEqual(tickets.parse_time("2026-03-02T09:15:02Z"), datetime(2026, 3, 2, 9, 15, 2, tzinfo=timezone.utc))
        self.assertEqual(tickets.parse_time("2026-03-02T10:15:02.250+01:00"), datetime(2026, 3, 2, 9, 15, 2, 250000, tzinfo=timezone.utc))
        with self.assertRaises(ValueError):
            tickets.parse_time("pending")

    def test_sheet_times(self):
        self.assertEqual(escalations.parse_time("2026-03-02 10:05", PLUS1), datetime(2026, 3, 2, 10, 5, tzinfo=PLUS1))
        self.assertEqual(escalations.parse_time("02.03.2026 10:05", PLUS1), datetime(2026, 3, 2, 10, 5, tzinfo=PLUS1))

    def test_switch_times(self):
        self.assertEqual(calls.parse_epoch("1772442902.75"), datetime(2026, 3, 2, 9, 15, 2, tzinfo=timezone.utc))
        self.assertEqual(calls.parse_epoch("1772442902"), datetime(2026, 3, 2, 9, 15, 2, tzinfo=timezone.utc))

    def test_chat_times(self):
        self.assertEqual(chats.parse_ms(1772442902750), datetime(2026, 3, 2, 9, 15, 3, tzinfo=timezone.utc))
        self.assertEqual(chats.parse_ms(1772442902250), datetime(2026, 3, 2, 9, 15, 2, tzinfo=timezone.utc))
        with self.assertRaises(ValueError):
            chats.parse_ms("1772442902750")

    def test_roster(self):
        s = roster.parse_line("ana 02/03/26 22:00-06:00", PLUS1)
        self.assertEqual((s.start, s.end), (datetime(2026, 3, 2, 22, 0, tzinfo=PLUS1), datetime(2026, 3, 3, 6, 0, tzinfo=PLUS1)))
        s = roster.parse_line("ben 02/03/26 16:00-24:00", PLUS1)
        self.assertEqual(s.end, datetime(2026, 3, 3, 0, 0, tzinfo=PLUS1))
        self.assertEqual(roster.parse_day("09/03/26"), date(2026, 3, 9))

    def test_closures(self):
        self.assertEqual(closures.parse_date("2026-03-06"), date(2026, 3, 6))
        self.assertEqual(closures.parse_date("03/08/2026"), date(2026, 3, 8))


if __name__ == "__main__":
    unittest.main()
