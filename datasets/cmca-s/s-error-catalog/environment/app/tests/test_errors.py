import unittest

from shipclient.errors import ErrorInfo, describe


class DescribeTest(unittest.TestCase):
    def test_known_code(self):
        self.assertEqual(describe("AUTH-001"), ErrorInfo(401, False, "Missing credentials"))

    def test_unknown_code(self):
        with self.assertRaises(KeyError):
            describe("XYZ-000")


if __name__ == "__main__":
    unittest.main()
