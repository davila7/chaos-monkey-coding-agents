import unittest
from datetime import datetime, timezone

from shipclient.retry import retry_delay

NOW = datetime(2026, 9, 16, 10, 0, 0, tzinfo=timezone.utc)


class RetryDelayTest(unittest.TestCase):
    def test_first_retry_of_a_get(self):
        self.assertEqual(retry_delay("GET", {}, 1, 503, {}, NOW), 0.25)

    def test_not_found_is_final(self):
        self.assertIsNone(retry_delay("GET", {}, 1, 404, {}, NOW))


if __name__ == "__main__":
    unittest.main()
