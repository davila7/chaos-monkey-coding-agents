"""The command line."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.support import APP, dataset_with

CONFIGS = {
    "web-2": "%include net.conf\n[server]\nworkers = 4\ntimeout = 1m30s\ntags = blue, green\nurl = https://${domain}:${port}/\n",
    "web-1": "name = web-1\n[defaults]\ndomain = one.example\n[server]\nmax_body = 64KiB\ndebug = off\n",
    "bad-1": "[server]\nport = eighty\n",
    "bad-2": "%include missing.conf\n",
}


def layercfg(*args):
    return subprocess.run([sys.executable, "-B", "-m", "layercfg", *args], cwd=APP, capture_output=True, text=True)


class CliTest(unittest.TestCase):
    def setUp(self):
        self.ds, tmp = dataset_with(CONFIGS)
        self.addCleanup(tmp.cleanup)
        self.data = str(self.ds.root)

    def test_resolve(self):
        r = layercfg("resolve", "web-2", "--data", self.data)
        self.assertEqual(r.returncode, 0, r.stderr)
        doc = json.loads(r.stdout)
        self.assertEqual(list(doc), ["config", "includes", "settings"])
        self.assertEqual(doc["settings"]["server"], {"host": "base.internal", "port": 9000, "tags": ["blue", "green"], "timeout": 90000,
                                                     "url": "https://mini.example:9000/", "workers": 4})
        self.assertEqual(list(doc["settings"]), ["defaults", "server", "server.tls"])
        self.assertTrue(r.stdout.startswith('{\n  "config": "web-2",\n'))

    def test_get(self):
        r = layercfg("get", "web-1", "server.max_body", "--data", self.data)
        self.assertEqual((r.returncode, r.stdout), (0, "65536\n"))
        r = layercfg("get", "web-2", "Server.TLS.port", "--data", self.data)
        self.assertEqual(r.stdout, "9443\n")
        r = layercfg("get", "web-1", "server.nothing", "--data", self.data)
        self.assertEqual(r.returncode, 1)

    def test_errors(self):
        r = layercfg("resolve", "bad-1", "--data", self.data)
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stderr.startswith("ConversionError: "), r.stderr)
        r = layercfg("resolve", "nothing", "--data", self.data)
        self.assertEqual(r.returncode, 1)

    def test_run(self):
        with tempfile.TemporaryDirectory() as out:
            r = layercfg("run", "--out", out, "--data", self.data)
            self.assertEqual(r.returncode, 0, r.stderr)
            out = Path(out)
            self.assertEqual(sorted(p.name for p in (out / "resolved").iterdir()), ["web-1.json", "web-2.json"])
            summary = json.loads((out / "summary.json").read_text())
            self.assertEqual(summary, [{"config": "web-1", "sections": 3, "keys": 4, "includes": 0},
                                       {"config": "web-2", "sections": 3, "keys": 9, "includes": 2}])
            errors = json.loads((out / "errors.json").read_text())
            self.assertEqual([(e["config"], e["error"].split(":")[0]) for e in errors], [("bad-1", "ConversionError"), ("bad-2", "IncludeError")])

    def test_unreadable_schema_stops_the_run(self):
        (self.ds.root / "schema.json").write_text("{not json")
        with tempfile.TemporaryDirectory() as out:
            r = layercfg("run", "--out", out, "--data", self.data)
        self.assertEqual(r.returncode, 1)
        self.assertIn("SchemaError", r.stderr)
