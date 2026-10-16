import unittest

from tests.support import run


def first_column(text):
    return [line.split()[0] for line in text.splitlines()[2:]]


class QueryTest(unittest.TestCase):
    def test_sort_descending(self):
        r = run("query", "orders", "--fields", "id,total", "--sort=-total")
        self.assertEqual(first_column(r.text), ["13", "16", "11", "12", "15"])

    def test_nulls_last_both_directions(self):
        self.assertEqual(first_column(run("query", "people", "--fields", "id,score", "--sort", "score").text), ["4", "1", "3", "2"])
        self.assertEqual(first_column(run("query", "people", "--fields", "id,score", "--sort=-score").text)[-1], "2")

    def test_limit(self):
        self.assertEqual(len(run("query", "orders", "--limit", "2").text.splitlines()), 4)


if __name__ == "__main__":
    unittest.main()
