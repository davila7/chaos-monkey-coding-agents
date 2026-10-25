import tempfile
import unittest
from pathlib import Path

from tests.support import FIXTURES

from orbis.postal import AddressError
from orbis.postal.records import read_records


class RecordsTest(unittest.TestCase):
    def write(self, name, text):
        d = Path(tempfile.mkdtemp())
        p = d / name
        p.write_text(text, encoding="utf-8")
        return p

    def test_jsonl_and_csv_agree(self):
        jsonl = read_records(FIXTURES / "addresses.jsonl")
        csv_ = read_records(FIXTURES / "addresses.csv")
        self.assertEqual(csv_, jsonl[: len(csv_)])

    def test_defaults_and_cleanup(self):
        p = self.write("a.jsonl", '{"country": "de", "city": "  Bad   Homburg "}\n\n{"id": 7, "country": "FR", "number": 12}\n')
        a, b = read_records(p)
        self.assertEqual((a.id, a.country, a.city), ("1", "DE", "Bad Homburg"))
        self.assertEqual((b.id, b.number), ("7", "12"))

    def test_errors(self):
        cases = {
            "bad.jsonl": '{"country": "DE"\n',
            "unknown.jsonl": '{"country": "DE", "floor": "3"}\n',
            "nocountry.jsonl": '{"city": "Berlin"}\n',
            "dup.jsonl": '{"id": "a", "country": "DE"}\n{"id": "a", "country": "FR"}\n',
            "type.jsonl": '{"country": "DE", "city": ["Berlin"]}\n',
        }
        for name, text in cases.items():
            with self.subTest(name=name), self.assertRaises(AddressError):
                read_records(self.write(name, text))

    def test_missing_file(self):
        with self.assertRaises(AddressError):
            read_records(FIXTURES / "nope.jsonl")


if __name__ == "__main__":
    unittest.main()
