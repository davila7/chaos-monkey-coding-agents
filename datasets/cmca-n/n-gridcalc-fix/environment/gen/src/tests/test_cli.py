import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.support import APP, MINI


def cli(*args):
    return subprocess.run([sys.executable, "-B", "-m", "gridcalc", *args], cwd=APP, capture_output=True, text=True)


class RunTest(unittest.TestCase):
    # overview.md 4.4, output.md 3 and 4
    def test_run(self):
        with tempfile.TemporaryDirectory() as td:
            r = cli("run", "--data", str(MINI), "--out", td)
            self.assertEqual(r.returncode, 0, r.stderr)
            out = Path(td)
            self.assertEqual(sorted(p.name for p in (out / "sheets").iterdir()), ["budget.json", "units.json"])
            self.assertEqual(json.loads((out / "summary.json").read_text()), [
                {"sheet": "budget", "cells": 5, "formulas": 3, "errors": 0},
                {"sheet": "units", "cells": 6, "formulas": 3, "errors": 1},
            ])
            errors = json.loads((out / "errors.json").read_text())
            self.assertEqual([e["sheet"] for e in errors], ["twice"])
            self.assertTrue(errors[0]["error"].startswith("SheetError: "))

    # output.md 2, 5
    def test_document_format(self):
        with tempfile.TemporaryDirectory() as td:
            cli("run", "--data", str(MINI), "--out", td)
            text = (Path(td) / "sheets" / "budget.json").read_text(encoding="utf-8")
        self.assertTrue(text.endswith("}\n"))
        self.assertIn('\n  "cells": [\n    {\n      "cell": "A1",', text)
        self.assertEqual(json.loads(text), {"sheet": "budget", "cells": [
            {"cell": "A1", "type": "number", "value": 120},
            {"cell": "A2", "type": "text", "value": "rent"},
            {"cell": "B1", "type": "number", "value": 132, "formula": "=A1*110%", "refs": ["A1"]},
            {"cell": "B2", "type": "number", "value": 18.86, "formula": "=ROUND(B1/7, 2)", "refs": ["B1"]},
            {"cell": "B3", "type": "text", "value": "total 132", "formula": '="total "&B1', "refs": ["B1"]},
        ]})


class CommandTest(unittest.TestCase):
    # overview.md 4.2, 4.3
    def test_cell(self):
        r = cli("cell", "units", "b1", "--data", str(MINI))
        self.assertEqual((r.returncode, r.stdout), (0, "1.75\n"))
        r = cli("cell", "units", "B2", "--data", str(MINI))
        self.assertEqual(r.stdout, '"#DIV/0!"\n')

    def test_missing(self):
        r = cli("cell", "units", "C9", "--data", str(MINI))
        self.assertEqual(r.returncode, 1)
        r = cli("show", "twice", "--data", str(MINI))
        self.assertEqual(r.returncode, 1)
        self.assertIn("SheetError", r.stderr)

    def test_show(self):
        r = cli("show", "units", "--data", str(MINI))
        self.assertEqual(r.returncode, 0)
        self.assertEqual([c["value"] for c in json.loads(r.stdout)["cells"]], [1500, 250, "kg", 1.75, "#DIV/0!", 2])
