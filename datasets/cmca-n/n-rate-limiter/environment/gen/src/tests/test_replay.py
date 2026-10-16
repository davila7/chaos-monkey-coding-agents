import unittest

from frontdoor.http.clientip import log_client
from frontdoor.http.headers import Headers
from frontdoor.timeutil import format_ts, parse_ts
from frontdoor.trace.request import Request
from tests.support import BASE, replay, req


class ReplayTest(unittest.TestCase):
    def test_statuses(self):
        r = replay(BASE, [
            req("a", "2025-05-06T10:00:00.000Z"),
            req("b", "2025-05-06T10:00:00.001Z", path="/nothing"),
            req("c", "2025-05-06T10:00:00.002Z", method="delete"),
            req("d", "2025-05-06T10:00:00.003Z", key="nope"),
            req("e", "2025-05-06T10:00:00.004Z", path="/healthz", key=None),
        ])
        self.assertEqual(r.status, 0, r.err)
        self.assertEqual([d["status"] for d in r.decisions], [200, 404, 405, 401, 200])
        self.assertEqual(r.by_id("c")["headers"], {"Allow": "GET, POST"})
        self.assertEqual(r.by_id("e")["tenant"], None)
        self.assertEqual(r.summary, {"requests": 5, "status": {"200": 2, "404": 1, "405": 1, "401": 1},
                                     "routes": {"orders": 3, "(none)": 1, "health": 1}})
        self.assertEqual(r.out, "replayed 5 requests\n")

    def test_files_in_order(self):
        r = replay(BASE, [req("x", "2025-05-06T10:00:01.000Z")], [req("y", "2025-05-06T10:00:00.000Z")])
        self.assertEqual([d["id"] for d in r.decisions], ["x", "y"])

    def test_bad_trace_writes_nothing(self):
        r = replay(BASE, [req("x", "2025-05-06 10:00:01")])
        self.assertEqual(r.status, 3)
        self.assertEqual(r.decisions, [])

    def test_log_client(self):
        h = Headers([["x-forwarded-for", " 203.0.113.5 , 10.20.0.1"], ["X-Forwarded-For", "9.9.9.9"]])
        self.assertEqual(log_client(Request("i", 0, "10.20.0.1", "GET", "/", h)), "203.0.113.5")
        self.assertEqual(log_client(Request("i", 0, "10.20.0.1", "GET", "/", Headers([]))), "10.20.0.1")

    def test_timestamps(self):
        self.assertEqual(parse_ts("1970-01-01T00:00:01.250Z"), 1250)
        self.assertEqual(format_ts(parse_ts("2025-05-06T10:00:00.007Z")), "2025-05-06T10:00:00.007Z")


if __name__ == "__main__":
    unittest.main()
