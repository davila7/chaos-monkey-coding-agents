import json
import unittest
from datetime import datetime, timezone

from yard.quayline import Booking, Response, Status, get_booking


class GetBookingTest(unittest.TestCase):
    def test_booked(self):
        sent = []

        def transport(method, path, params, body):
            sent.append((method, path, dict(params), body))
            booking = {
                "id": "bk_4f2a91",
                "dock_id": "D07",
                "starts_at": "2026-10-06T13:30:00Z",
                "ends_at": "2026-10-06T14:15:00Z",
                "carrier": {"name": "Northwind Haulage", "scac": "NWHL"},
                "trailer_number": "TR-4471",
                "status": "booked",
                "cancellation": None,
            }
            return Response(200, {"Content-Type": "application/json"}, json.dumps(booking).encode())

        got = get_booking(transport, "bk_4f2a91")
        want = Booking("bk_4f2a91", "D07", datetime(2026, 10, 6, 13, 30, tzinfo=timezone.utc), 45, "Northwind Haulage", "NWHL", "TR-4471", Status.CONFIRMED, None)
        self.assertEqual(got, want)
        self.assertEqual(sent, [("GET", "/v4/bookings/bk_4f2a91", {}, None)])


if __name__ == "__main__":
    unittest.main()
