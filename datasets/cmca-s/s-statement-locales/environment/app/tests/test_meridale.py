import json
import unittest
from datetime import date
from decimal import Decimal

from statements.meridale import Merchant, Response, monthly_statement


class MonthlyStatementTest(unittest.TestCase):
    def test_one_day(self):
        def transport(method, path, params, body):
            report = {
                "merchant_id": "m_1d40",
                "currency": "USD",
                "tz": "America/New_York",
                "locale": "en-US",
                "days": [{"day": "2026-10-14", "gross": "1520.4", "fees": "44.09", "refunds": "12"}],
            }
            return Response(200, {"Content-Type": "application/json"}, json.dumps(report).encode())

        got = monthly_statement(transport, Merchant("m_1d40", "America/New_York", "en_US.UTF-8", "USD"), 2026, 10)
        self.assertEqual(len(got.lines), 1)
        line = got.lines[0]
        self.assertEqual((line.day, line.gross, line.fees, line.refunds, line.net), (date(2026, 10, 14), Decimal("1520.40"), Decimal("44.09"), Decimal("12.00"), Decimal("1464.31")))
        self.assertEqual(line.net_text, "USD 1,464.31")
        self.assertEqual((got.total_net, got.total_text), (Decimal("1464.31"), "USD 1,464.31"))


if __name__ == "__main__":
    unittest.main()
