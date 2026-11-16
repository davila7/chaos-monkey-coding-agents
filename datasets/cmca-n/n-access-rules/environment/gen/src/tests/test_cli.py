"""The command line against the reviewed outputs in tests/expected."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXPECTED = ROOT / "tests" / "expected"


def run(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(ROOT)}
    return subprocess.run([sys.executable, "-m", "docshelf", *args], cwd=cwd, env=env, capture_output=True, text=True)


class ReviewedOutputs(unittest.TestCase):
    def test_reviewed(self):
        for case in json.loads((EXPECTED / "index.json").read_text()):
            want = json.loads((EXPECTED / f"{case['name']}.json").read_text())
            with self.subTest(case=case["name"]):
                if case["changes"]:
                    with tempfile.TemporaryDirectory() as tmp:
                        shutil.copytree(ROOT / case["args"][1], Path(tmp) / case["args"][1])
                        r = run(Path(tmp), *case["args"])
                        files = {p.name: p.read_text(encoding="utf-8") for p in sorted((Path(tmp) / case["args"][1]).iterdir())}
                    self.assertEqual(files, want["files"])
                else:
                    r = run(ROOT, *case["args"])
                self.assertEqual((r.returncode, r.stdout, r.stderr), (want["code"], want["stdout"], want["stderr"]))


class Errors(unittest.TestCase):
    def test_missing_folder(self):
        r = run(ROOT, "list", "samples/nowhere", "--as", "ana", "--at", "2026-05-04T10:00")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stderr, "docshelf: error: samples/nowhere: not a folder\n")

    def test_unknown_user(self):
        r = run(ROOT, "list", "samples/north", "--as", "nobody", "--at", "2026-05-04T10:00")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stderr, "docshelf: error: unknown user: nobody\n")

    def test_bad_time(self):
        r = run(ROOT, "list", "samples/north", "--as", "nobody", "--at", "2026-05-04 10:00")
        self.assertEqual(r.returncode, 2)
        self.assertIn("not a time (YYYY-MM-DDTHH:MM): '2026-05-04 10:00'", r.stderr)

    def test_unknown_document(self):
        users = (ROOT / "samples" / "north" / "users.csv").read_text().splitlines()
        r = run(ROOT, "show", "samples/north", "D-1", "--as", users[1].split(",")[0], "--at", "2026-05-04T10:00")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stderr, "docshelf: error: no such document: D-1\n")


if __name__ == "__main__":
    unittest.main()
