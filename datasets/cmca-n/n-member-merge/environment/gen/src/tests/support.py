"""Helpers: a small data directory in a temporary folder, run through clubroll.cli.main."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from clubroll.cli import main

NOW = "2026-11-02T09:15:00Z"
SETTINGS = {"phone": {"country": "44", "trunk": "0"},
            "email": {"dotless_domains": ["gmail.com"], "domain_aliases": {"googlemail.com": "gmail.com"}}}


def member(n, name, *, email="", phone="", dob="", joined="2020-01-01", expires="", marketing="", tags=(),
           updated="2024-01-01T00:00:00Z"):
    return {"id": f"M-{n:04d}", "name": name, "email": email, "phone": phone, "dob": dob, "joined": joined,
            "expires": expires, "marketing": marketing, "tags": tags if isinstance(tags, str) else list(tags),
            "updated": updated}


class Workspace:
    def __init__(self, case: unittest.TestCase, members=(), aliases=None, payments=(), audit=(), settings=SETTINGS,
                 keep_apart=None):
        self._tmp = tempfile.TemporaryDirectory()
        case.addCleanup(self._tmp.cleanup)
        self.data = Path(self._tmp.name) / "data"
        self.data.mkdir()
        doc = {"format": 3, "members": list(members)}
        self._write("members.json", json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        self._write("aliases.json", json.dumps(aliases or {}, indent=2) + "\n")
        self._write("payments.csv", "".join(f"{line}\n" for line in ["payment,member,day,amount", *payments]))
        self._write("audit.jsonl", "".join((a if isinstance(a, str) else json.dumps(a, separators=(",", ":"))) + "\n"
                                           for a in audit))
        if settings is not None:
            self._write("settings.json", json.dumps(settings, indent=2) + "\n")
        if keep_apart is not None:
            self._write("keep_apart.csv", "".join(f"{line}\n" for line in ["first,second,note", *keep_apart]))

    def _write(self, name, text):
        (self.data / name).write_text(text, encoding="utf-8")

    def run(self, *argv, by=None, now=NOW):
        """Returns (exit status, standard output, error code or '')."""
        out, err = io.StringIO(), io.StringIO()
        args = ["--data", str(self.data), "--now", now] + (["--by", by] if by else []) + list(argv)
        with contextlib.redirect_stderr(err):
            status = main(args, out=out)
        text = err.getvalue()
        code = text.split(":")[2].strip() if text.startswith("clubroll: error:") else ""
        return status, out.getvalue(), code

    def text(self, name) -> str:
        return (self.data / name).read_text(encoding="utf-8")

    def members(self) -> list[dict]:
        return json.loads(self.text("members.json"))["members"]

    def snapshot(self) -> dict:
        return {p.name: p.read_text(encoding="utf-8") for p in sorted(self.data.iterdir())}
