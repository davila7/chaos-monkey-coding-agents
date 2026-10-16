import unittest

from tests.support import run


class CollectionsTest(unittest.TestCase):
    def test_counts_live_records(self):
        r = run("collections")
        self.assertEqual(r.status, 0)
        lines = r.text.splitlines()
        self.assertEqual(lines[2].split(), ["orders", "5", "2"])
        self.assertEqual(lines[3].split(), ["people", "4", "1"])

    def test_names_only(self):
        self.assertEqual(run("collections", "--names-only").text, "orders\npeople\n")


class SchemaTest(unittest.TestCase):
    def test_json(self):
        r = run("schema", "orders", "--json")
        self.assertEqual(r.status, 0)
        self.assertIn('"ship.city"', r.text)

    def test_unknown_collection(self):
        r = run("schema", "nope")
        self.assertEqual(r.status, 2)
        self.assertEqual(r.out, b"")
        self.assertTrue(r.err.startswith("tally: error: "))


if __name__ == "__main__":
    unittest.main()
