"""Shared files (include.md)."""

import unittest

from layercfg.errors import IncludeError, ParseError

from tests.support import resolved, settings


class IncludeTest(unittest.TestCase):
    def test_values_apply_where_the_directive_is(self):
        s = settings("%include base.conf\n[server]\nport = 1\n")
        self.assertEqual(s["server"], {"host": "base.internal", "port": 1})
        s = settings("[server]\nport = 1\n%include base.conf\n")
        self.assertEqual(s["server"]["port"], 8080)

    def test_nested(self):
        doc = resolved("%include net.conf\n%include log.conf\n[server]\nhost = edge\n")
        self.assertEqual(doc["includes"], ["net.conf", "base.conf", "log.conf"])
        self.assertEqual(doc["settings"]["server"], {"host": "edge", "port": 9000})
        self.assertEqual(doc["settings"]["server.tls"], {"port": 9443})
        self.assertEqual(doc["settings"]["logging"], {"dir": "/srv/mini/log", "level": "info"})

    def test_shared_files_start_in_main(self):
        doc = resolved("%include extra.conf\n[server]\nport = 2\n", {"extra.conf": "owner = ops\n[cache]\nttl = 5s\n"})
        self.assertEqual(doc["settings"]["main"], {"owner": "ops"})

    def test_no_includes(self):
        self.assertEqual(resolved("[server]\nport = 3\n")["includes"], [])

    def test_cycles(self):
        for text in ("%include ring-a.conf\n", "%include self.conf\n"):
            with self.subTest(text=text):
                with self.assertRaises(IncludeError):
                    settings(text, {"self.conf": "%include self.conf\n"})

    def test_missing_file(self):
        with self.assertRaises(IncludeError):
            settings("%include nothere.conf\n")

    def test_errors_in_shared_files(self):
        with self.assertRaises(ParseError) as cm:
            settings("%include broken.conf\n", {"broken.conf": "[server]\nno separator here\n"})
        self.assertIn("broken.conf", str(cm.exception))
