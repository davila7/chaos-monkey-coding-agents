import unittest

from tests.support import run


class CountTest(unittest.TestCase):
    def test_all(self):
        self.assertEqual(run("count", "orders").text, "5\n")

    def test_where_equal_text(self):
        self.assertEqual(run("count", "orders", "--where", "status=open").text, "3\n")
        self.assertEqual(run("count", "orders", "--where", "total=19.99").text, "1\n")

    def test_nulls_never_match(self):
        self.assertEqual(run("count", "orders", "--where", "paid=").text, "0\n")

    def test_several_conditions(self):
        self.assertEqual(run("count", "orders", "--where", "status=open", "--where", "ship.city=Leeds").text, "1\n")

    def test_unknown_field(self):
        self.assertEqual(run("count", "orders", "--where", "colour=red").status, 2)


if __name__ == "__main__":
    unittest.main()
