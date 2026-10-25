"""The command line."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.support import APP, dataset_with

RECORDS = [
    {"id": "M-0101", "label": "Shaft", "readings": ["2.54 cm", "1.00 in"], "reduce": "sum", "target": "mm"},
    {"id": "M-0104", "label": "Kiln", "readings": ["451 degF"], "target": "degC"},
    {"id": "M-0103", "readings": ["3 furlong"]},
    {"id": "M-0102", "label": "Pump A", "readings": ["120.0 L/min"], "target": "L/s"},
]


def measure(*args):
    return subprocess.run([sys.executable, "-B", "-m", "measure", *args], cwd=APP, capture_output=True, text=True)


class CliTest(unittest.TestCase):
    def setUp(self):
        self.ds, tmp = dataset_with(RECORDS)
        self.addCleanup(tmp.cleanup)
        self.data = str(self.ds.root)

    def test_convert(self):
        r = measure("convert", "6.0 ft", "m", "--data", self.data)
        self.assertEqual((r.returncode, r.stdout), (0, "1.8 m\n"))
        r = measure("convert", "1.50 MJ", "--data", self.data)
        self.assertEqual(r.stdout, "1.50e6 kg*m^2/s^2\n")
        r = measure("convert", "451 degF", "K", "--data", self.data)
        self.assertEqual(r.stdout, "506 K\n")

    def test_report(self):
        r = measure("report", "M-0101", "--data", self.data)
        self.assertEqual(r.returncode, 0, r.stderr)
        doc = json.loads(r.stdout)
        self.assertEqual((doc["value"], doc["unit"], doc["si"]), ("50.8", "mm", {"value": "0.0508", "unit": "m"}))
        self.assertTrue(r.stdout.startswith('{\n  "id": "M-0101",'))

    def test_show(self):
        r = measure("show", "M-0104", "--data", self.data)
        self.assertEqual(r.stdout, "M-0104  Kiln\n  233 degC\n  = 506 K\n  single of 1 reading(s), 3 significant figure(s), absolute\n")

    def test_error(self):
        r = measure("report", "M-0103", "--data", self.data)
        self.assertEqual((r.returncode, r.stdout), (1, ""))
        self.assertIn("UnitError", r.stderr)
        self.assertEqual(measure("show", "M-0999", "--data", self.data).returncode, 1)
        self.assertEqual(measure("convert", "3 parsec", "--data", self.data).returncode, 1)

    def test_run(self):
        with tempfile.TemporaryDirectory() as out:
            r = measure("run", "--data", self.data, "--out", out)
            self.assertEqual(r.returncode, 0, r.stderr)
            out = Path(out)
            self.assertEqual(sorted(p.name for p in (out / "reports").iterdir()), ["M-0101.json", "M-0102.json", "M-0104.json"])
            errors = json.loads((out / "errors.json").read_text())
            self.assertEqual([e["record"] for e in errors], ["M-0103"])
            self.assertTrue(errors[0]["error"].startswith("UnitError: "))
            rows = json.loads((out / "summary.json").read_text())
            self.assertEqual([(r["id"], r["value"], r["unit"]) for r in rows], [("M-0101", "50.8", "mm"), ("M-0102", "2.000", "L/s"), ("M-0104", "233", "degC")])
            self.assertEqual(list(rows[0]), ["id", "dimension", "value", "unit"])

    def test_run_without_units_table(self):
        with tempfile.TemporaryDirectory() as out:
            (self.ds.root / "units.json").unlink()
            self.assertEqual(measure("run", "--data", self.data, "--out", out).returncode, 1)
