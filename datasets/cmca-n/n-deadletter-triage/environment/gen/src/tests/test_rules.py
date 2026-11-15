import unittest

from quayside import dedupe, lease, retry, schema

from .support import MINUTE, at, cfg, email, refund


def fresh() -> dict:
    return {"failures": 0}


class Results(unittest.TestCase):
    def test_ok_and_rejected(self):
        job = cfg().job("email.send")
        self.assertEqual(retry.settle(fresh(), "ok", 0, job, at(0)), ("done",))
        self.assertEqual(retry.settle(fresh(), "rejected", 0, job, at(0)), ("dead", "rejected"))

    def test_errors_back_off_then_run_out(self):
        job = cfg().job("email.send")
        m = fresh()
        waits = []
        for _ in range(3):
            kind, ready = retry.settle(m, "error", 0, job, at(0))
            self.assertEqual(kind, "retry")
            waits.append((ready - at(0)) // MINUTE)
        self.assertEqual(waits, [1, 2, 4])
        self.assertEqual(retry.settle(m, "error", 0, job, at(0)), ("dead", "attempts-exhausted"))

    def test_backoff_cap(self):
        job = cfg().job("refund.issue")
        self.assertEqual([retry.backoff_ms(n, job) // MINUTE for n in range(1, 6)], [2, 4, 8, 15, 15])


class Leases(unittest.TestCase):
    def test_without_heartbeat(self):
        self.assertEqual(lease.expires_at(at(0), 11 * MINUTE, 10 * MINUTE, 0, False), at(10))
        self.assertIsNone(lease.expires_at(at(0), 9 * MINUTE, 10 * MINUTE, 0, False))

    def test_heartbeat_keeps_a_long_handler(self):
        c = cfg()
        job = c.job("email.send")
        interval = lease.heartbeat_interval(c, job)
        self.assertEqual(interval, 200_000)
        self.assertIsNone(lease.expires_at(at(0), 45 * MINUTE, job.visibility_ms, interval, True))

    def test_lease_at_a_stop(self):
        self.assertEqual(lease.lease_end(at(0), at(7), 10 * MINUTE, 200_000, True), at(0) + 400_000 + 10 * MINUTE)
        self.assertEqual(lease.lease_end(at(0), at(7), 10 * MINUTE, 200_000, False), at(10))


class Keys(unittest.TestCase):
    def test_schema_2_key(self):
        self.assertEqual(dedupe.key_of("email.send", email("o7")), "email.send:em-o7-confirm")

    def test_order_fallback(self):
        p = email("o7")
        del p["idem_key"]
        self.assertEqual(dedupe.key_of("email.send", p), "email.send:order:o7")

    def test_digest_ignores_sent_at(self):
        a, b = email("o7"), email("o7", sent_at="2027-01-02T00:00:00.000Z")
        self.assertEqual(dedupe.digest(a), dedupe.digest(b))
        self.assertNotEqual(dedupe.digest(a), dedupe.digest(email("o8")))

    def test_store(self):
        s = dedupe.KeyStore()
        self.assertEqual(s.check("k", "m1", "d1", at(0)), ("run", None))
        self.assertEqual(s.check("k", "m1", "d1", at(1)), ("run", None))
        self.assertEqual(s.check("k", "m2", "d1", at(1)), ("duplicate", "m1"))
        self.assertEqual(s.check("k", "m3", "d2", at(1)), ("conflict", "m1"))
        s.complete("k", "m1", at(10))
        self.assertEqual(s.check("k", "m4", "d2", at(9)), ("conflict", "m1"))
        self.assertEqual(s.check("k", "m4", "d2", at(10)), ("run", None))
        s.release("k", "m1")
        self.assertIn("k", s.entries)
        s.release("k", "m4")
        self.assertNotIn("k", s.entries)


class Payloads(unittest.TestCase):
    def test_accepts_listed_fields(self):
        self.assertIsNone(schema.check("email.send", email(), cfg()))
        self.assertIsNone(schema.check("refund.issue", refund(), cfg()))

    def test_missing_field(self):
        p = refund()
        del p["amount"]
        self.assertEqual(schema.check("refund.issue", p, cfg()), "missing amount")

    def test_version(self):
        self.assertIsNotNone(schema.check("email.send", email(v=1), cfg()))
        self.assertIsNotNone(schema.check("email.send", email(v="2"), cfg()))
        self.assertIsNotNone(schema.check("email.send", email(v=True), cfg()))
