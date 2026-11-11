"""Quoted values and escapes (syntax.md section 5)."""

import unittest

from layercfg.errors import ParseError
from layercfg.values import parse_value

from tests.support import settings


class QuotedTest(unittest.TestCase):
    def test_double_quoted(self):
        self.assertEqual(parse_value(' "a  b " ', "t"), ("a  b ", True))
        self.assertEqual(parse_value(r' "say \"hi\"\t\\ok\n"', "t"), ('say "hi"\t\\ok\n', True))

    def test_single_quoted(self):
        self.assertEqual(parse_value(r" 'C:\temp ${x}' ", "t"), (r"C:\temp ${x}", False))

    def test_comment_after_a_quote(self):
        self.assertEqual(parse_value(' "a # b"   # c', "t"), ("a # b", True))
        self.assertEqual(parse_value(" 'x'\t# c", "t"), ("x", False))

    def test_errors(self):
        for raw in (' "open', " 'open", r' "bad \q"', ' "a" b', " 'a'b", ' "a"#c', ' "end\\'):
            with self.subTest(raw=raw):
                with self.assertRaises(ParseError):
                    parse_value(raw, "t")


class EscapedDollarTest(unittest.TestCase):
    def test_escaped_dollar_is_literal(self):
        s = settings('[server]\nhost = h\na = "\\${host} is ${host}"\nb = "\\$\\$"\nc = "cost \\$5"\n')["server"]
        self.assertEqual(s, {"host": "h", "a": "${host} is h", "b": "$$", "c": "cost $5"})

    def test_single_quotes_are_never_expanded(self):
        s = settings("[server]\nhost = h\na = '${host} $$'\n")["server"]
        self.assertEqual(s["a"], "${host} $$")
