import json
import tempfile
import unittest
from pathlib import Path

from spokehouse import feeds, store
from spokehouse.errors import FeedError

from tests.support import state, when


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.file = self.dir / "state.json"
        self.file.write_text(store.render(state()), encoding="utf-8")
        (self.dir / "snapshots").mkdir()

    def test_save_next_revision(self):
        s = store.load(self.file)
        s["members"]["M1"]["trips"] += 1
        out = store.save(self.file, s, job="trips", at=when("2027-01-04T09:00:12Z"), snapshots=self.dir / "snapshots")
        self.assertEqual(out["meta"], {"rev": 8, "job": "trips", "at": "2027-01-04T09:00:12Z", "version": "4.2.0"})
        self.assertEqual(store.load(self.file), out)
        self.assertEqual([p.name for p in (self.dir / "snapshots").iterdir()], ["000008-20270104T090012Z-trips.json"])

    def test_data_leaves_meta_out(self):
        self.assertNotIn("meta", store.data(state()))


class FeedTests(unittest.TestCase):
    def write(self, text: str) -> Path:
        p = Path(tempfile.mkdtemp()) / "feed.jsonl"
        p.write_text(text, encoding="utf-8")
        return p

    def test_read(self):
        head = json.dumps({"batch": "T1", "kind": "trips", "count": 1, "delivered": "2027-01-04T09:00:00Z"})
        out = feeds.read_batch(self.write(head + '\n{"trip": "R1"}\n'))
        self.assertEqual(out, {"batch": "T1", "kind": "trips", "records": [{"trip": "R1"}]})

    def test_truncated(self):
        head = json.dumps({"batch": "T1", "kind": "trips", "count": 1, "delivered": "2027-01-04T09:00:00Z"})
        with self.assertRaises(FeedError):
            feeds.read_batch(self.write(head + '\n{"trip": "R1", "mem\n'))


if __name__ == "__main__":
    unittest.main()
