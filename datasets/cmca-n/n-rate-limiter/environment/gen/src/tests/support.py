"""Helpers: small configurations and traces in a temporary directory, run through frontdoor.cli.main."""

import contextlib
import io
import json
import tempfile
from pathlib import Path

from frontdoor.cli import main

BASE = """
[[route]]
name = "orders"
prefix = "/api/v1/orders"
methods = ["GET", "POST"]

[[route]]
name = "health"
prefix = "/healthz"
public = true

[tenants.blue]
keys = ["kb"]

[tenants.green]
keys = ["kg"]
"""


def req(id, ts, path="/api/v1/orders", method="GET", peer="198.51.100.1", key="kb", headers=()):
    h = [["X-Api-Key", key]] if key else []
    h += [list(x) for x in headers]
    return {"id": id, "ts": ts, "peer": peer, "method": method, "path": path, "headers": h}


class Run:
    def __init__(self, status, out, err, decisions, summary):
        self.status, self.out, self.err = status, out, err
        self.decisions, self.summary = decisions, summary

    def by_id(self, id):
        return next(d for d in self.decisions if d["id"] == id)


def replay(config_text: str, *traces) -> Run:
    """traces: lists of request dicts, one list per trace file."""
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "edge.toml").write_text(config_text, encoding="utf-8")
        names = []
        for i, lines in enumerate(traces):
            p = d / f"t{i}.jsonl"
            p.write_text("".join(json.dumps(x) + "\n" for x in lines), encoding="utf-8")
            names.append(str(p))
        status, out, err = cli("replay", "--config", str(d / "edge.toml"), "--out", str(d / "out"), *names)
        decisions, summary = [], None
        if (d / "out" / "decisions.jsonl").exists():
            decisions = [json.loads(x) for x in (d / "out" / "decisions.jsonl").read_text(encoding="utf-8").splitlines()]
            summary = json.loads((d / "out" / "summary.json").read_text(encoding="utf-8"))
        return Run(status, out, err, decisions, summary)


def check(config_text: str):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "c.toml"
        p.write_text(config_text, encoding="utf-8")
        return cli("check", "--config", str(p))


def cli(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        status = main(list(argv))
    return status, out.getvalue(), err.getvalue()
