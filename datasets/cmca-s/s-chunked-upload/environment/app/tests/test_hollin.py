import json
import unittest

from archive.hollin import Response, StoredFile, file_info


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.sent = []

    def send(self, method, path, headers, body):
        self.sent.append((method, path, body))
        return self.responses.pop(0)

    def now(self):
        return 1_794_000_000.0


class FileInfoTest(unittest.TestCase):
    def test_stored(self):
        stored = {"file_id": "fl_3c90ae", "name": "scan-0042.pdf", "size": 182_330, "checksum": "q1Hk0mY3c2Xy8e0Hn0r4v0bq1a3o2b5m4c7d6e9f8g0-1"}
        transport = FakeTransport([Response(200, {"Content-Type": "application/json"}, json.dumps(stored).encode())])
        got = file_info(transport, "fl_3c90ae")
        self.assertEqual(got, StoredFile("fl_3c90ae", "scan-0042.pdf", 182_330, stored["checksum"]))
        self.assertEqual(transport.sent, [("GET", "/v3/files/fl_3c90ae", None)])


if __name__ == "__main__":
    unittest.main()
