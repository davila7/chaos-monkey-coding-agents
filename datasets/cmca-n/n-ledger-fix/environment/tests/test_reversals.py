import unittest
from datetime import date

from ledger.errors import UnmatchedReversal
from ledger.reversals import bookings
from ledger.statement import Entry

DEPOSIT = Entry("a1", date(2026, 2, 27), "Deposit", -30000)


class ReversalsTest(unittest.TestCase):
    def test_plain_entry(self):
        (b,) = bookings([DEPOSIT])
        self.assertEqual(b.month_date, date(2026, 2, 27))

    def test_reversal_is_booked_in_month_of_original(self):
        back = Entry("a2", date(2026, 3, 3), "Deposit returned", 30000, reverses="a1")
        self.assertEqual([b.month_date for b in bookings([DEPOSIT, back])], [date(2026, 2, 27)] * 2)

    def test_unknown_original(self):
        back = Entry("a2", date(2026, 3, 3), "Deposit returned", 30000, reverses="zz")
        with self.assertRaises(UnmatchedReversal):
            bookings([DEPOSIT, back])

    def test_reversal_of_a_reversal(self):
        back = Entry("a2", date(2026, 3, 3), "Deposit returned", 30000, reverses="a1")
        again = Entry("a3", date(2026, 3, 9), "Deposit charged again", -30000, reverses="a2")
        with self.assertRaises(UnmatchedReversal):
            bookings([DEPOSIT, back, again])

    def test_amount_must_cancel(self):
        back = Entry("a2", date(2026, 3, 3), "Deposit returned", 29999, reverses="a1")
        with self.assertRaises(UnmatchedReversal):
            bookings([DEPOSIT, back])


if __name__ == "__main__":
    unittest.main()
