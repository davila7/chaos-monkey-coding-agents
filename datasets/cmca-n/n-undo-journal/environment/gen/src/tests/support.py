"""Helpers: a small data directory in a temporary folder, run through binkeep.cli.main."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from binkeep.cli import main

ITEMS = [("BX-1042", "small carton", 12), ("TB-2201", "clear tape", 1), ("RL-3300", "label roll", 6)]
# bin, zone, pick_seq, status
BINS = [("A-01", "A", 30, "active"), ("A-02", "A", 20, "active"), ("B-01", "B", 10, "active"),
        ("B-02", "B", 40, "retired"), ("C-01", "C", 50, "active")]


class Workspace:
    def __init__(self, case: unittest.TestCase, stock=None, journal=(), bins=BINS, items=ITEMS):
        self._tmp = tempfile.TemporaryDirectory()
        case.addCleanup(self._tmp.cleanup)
        self.data = Path(self._tmp.name) / "data"
        self.data.mkdir()
        lines = ["sku,description,pack_size"] + [f"{s},{d},{p}" for s, d, p in items]
        (self.data / "items.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
        lines = ["bin,zone,pick_seq,status"] + [f"{b},{z},{n},{st}" for b, z, n, st in bins]
        (self.data / "bins.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
        state = {"format": 2, "stock": stock or {}}
        (self.data / "state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        text = "".join((line if isinstance(line, str) else json.dumps(line, separators=(",", ":"))) + "\n" for line in journal)
        (self.data / "journal.jsonl").write_text(text, encoding="utf-8")

    def run(self, *argv, by=None):
        """Returns (exit status, standard output, error code or '')."""
        out, err = io.StringIO(), io.StringIO()
        args = ["--data", str(self.data)] + (["--by", by] if by else []) + list(argv)
        with contextlib.redirect_stderr(err):
            status = main(args, out=out)
        text = err.getvalue()
        code = text.split(":")[2].strip() if text.startswith("binkeep: error:") else ""
        return status, out.getvalue(), code

    def state(self) -> dict:
        return json.loads((self.data / "state.json").read_text(encoding="utf-8"))["stock"]

    def state_text(self) -> str:
        return (self.data / "state.json").read_text(encoding="utf-8")

    def journal_lines(self) -> list[str]:
        return (self.data / "journal.jsonl").read_text(encoding="utf-8").splitlines()
