import json
import unittest

from books.penwick import Response, Transfer, get_transfer


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.sent = []

    def send(self, method, path, headers, body):
        self.sent.append((method, path, body))
        return self.responses.pop(0)

    def sleep(self, seconds):
        raise AssertionError("no wait expected")


class GetTransferTest(unittest.TestCase):
    def test_settled(self):
        transfer = {
            "id": "tr_8d1c40",
            "source": "acc_ops_eur",
            "destination": "acc_cust_1182",
            "amount": 2500,
            "currency": "EUR",
            "reference": "INV-2207",
            "status": "settled",
        }
        transport = FakeTransport([Response(200, {"Content-Type": "application/json"}, json.dumps(transfer).encode())])
        got = get_transfer(transport, "tr_8d1c40")
        self.assertEqual(got, Transfer("tr_8d1c40", "acc_ops_eur", "acc_cust_1182", 2500, "EUR", "INV-2207", "settled"))
        self.assertEqual(transport.sent, [("GET", "/v2/transfers/tr_8d1c40", None)])


if __name__ == "__main__":
    unittest.main()
