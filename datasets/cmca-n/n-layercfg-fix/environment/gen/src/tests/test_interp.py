"""References (interp.md)."""

import unittest

from layercfg.errors import InterpolationError

from tests.support import settings


class ReferenceTest(unittest.TestCase):
    def test_same_section(self):
        s = settings("[server]\nhost = edge\nport = 81\nurl = http://${host}:${port}/\n")["server"]
        self.assertEqual(s["url"], "http://edge:81/")

    def test_defaults_section(self):
        s = settings("[defaults]\nroot = /srv\n[server]\nlog = ${root}/log\n")
        self.assertEqual(s["server"]["log"], "/srv/log")

    def test_own_section_comes_first(self):
        s = settings("[defaults]\nroot = /srv\n[server]\nroot = /opt\nlog = ${root}/log\n")
        self.assertEqual(s["server"]["log"], "/opt/log")

    def test_other_section(self):
        s = settings("[db]\nhost = pg\n[Server]\ndsn = ${DB.host}/x\n")
        self.assertEqual(s["server"]["dsn"], "pg/x")

    def test_chains(self):
        s = settings("[defaults]\nroot = /srv\n[logging]\ndir = ${root}/log\nfile = ${dir}/main.log\n[server]\nlog = ${logging.file}\n")
        self.assertEqual(s["server"]["log"], "/srv/log/main.log")

    def test_dollar_signs(self):
        s = settings("[server]\ne = x\na = $$HOME\nb = cost $5\nc = $\nd = $$${e}\n")["server"]
        self.assertEqual(s, {"a": "$HOME", "b": "cost $5", "c": "$", "d": "$x", "e": "x"})

    def test_inserted_text_is_not_read_again(self):
        s = settings("[server]\na = '${b}'\nb = x\nc = ${a}\n")["server"]
        self.assertEqual(s["c"], "${b}")

    def test_references_are_typed_after_expansion(self):
        s = settings("[defaults]\np = 9100\n[server]\nflag = yes\nport = ${p}\ndebug = ${flag}\n")["server"]
        self.assertEqual((s["port"], s["debug"]), (9100, True))

    def test_errors(self):
        for text in ("[server]\na = ${missing}\n", "[server]\na = ${b}\nb = ${a}\n", "[server]\na = ${a}\n",
                     "[server]\na = ${b\n", "[server]\na = ${}\n", "[server]\na = ${x y}\n", "[server]\na = ${other.b}\n"):
            with self.subTest(text=text):
                with self.assertRaises(InterpolationError):
                    settings(text)
