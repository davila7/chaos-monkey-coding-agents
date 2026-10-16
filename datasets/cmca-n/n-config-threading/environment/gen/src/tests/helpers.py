"""Shared helpers for the quoter tests."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from quoter import settings

ROOT = Path(__file__).resolve().parent.parent

SMALL_BATCH = """id,from,to,weight,dims,residential,value
A1,DE-10115,FR-75001,2,30x20x10,,
A2,DE-10115,DE-80331,12.5,50x40x30,yes,
A3,DE-10115,US-10001,3,,,400
A4,DE-10115,XX-1234,2,,,
A5,DE-10115,FR-75001,2,30x20x10,,
A6,DE-10115,IT-90121,0.4,,no,
"""

MISSING_COLUMN = """id,from,weight
1,DE-10115,2
"""


def write_temp(case: unittest.TestCase, text: str, suffix: str) -> str:
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    case.addCleanup(os.unlink, path)
    return path


def run_cli(*argv: str, env: dict | None = None) -> subprocess.CompletedProcess:
    """Runs `python -m quoter` from the project root with a clean environment."""
    base = {k: v for k, v in os.environ.items() if not k.startswith("QUOTER_")}
    base.update(env or {})
    return subprocess.run([sys.executable, "-m", "quoter", *argv], cwd=ROOT, env=base, capture_output=True, text=True, timeout=60)


class SettingsCase(unittest.TestCase):
    """Starts every test from the fallback settings with caching off, so that
    results from one test are never reused by another."""

    def setUp(self) -> None:
        settings.reset()
        settings.configure(cache_enabled=False)

    def tearDown(self) -> None:
        settings.reset()
