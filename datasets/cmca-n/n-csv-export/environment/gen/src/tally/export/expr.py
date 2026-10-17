"""--where expressions (docs/export.md, section 5)."""

import re
from datetime import datetime
from decimal import Decimal

from tally.errors import UsageError
from tally.store.values import parse_date, parse_datetime, typed

KEYWORDS = {"and", "or", "not", "in", "is", "null", "true", "false"}
OPS = ("<=", ">=", "!=", "=", "<", ">", "~")
_PATH = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*")
_NUMBER = re.compile(r"-?\d+(\.\d+)?")


def tokenize(text: str) -> list:
    toks = []
    i = 0
    while i < len(text):
        c = text[i]
        if c.isspace():
            i += 1
            continue
        if c in "(),":
            toks.append(("punct", c))
            i += 1
            continue
        if c == "'":
            j = i + 1
            buf = []
            while True:
                if j >= len(text):
                    raise UsageError("--where: unterminated string")
                if text[j] == "'":
                    if j + 1 < len(text) and text[j + 1] == "'":
                        buf.append("'")
                        j += 2
                        continue
                    break
                buf.append(text[j])
                j += 1
            toks.append(("string", "".join(buf)))
            i = j + 1
            continue
        op = next((o for o in OPS if text.startswith(o, i)), None)
        if op:
            toks.append(("op", op))
            i += len(op)
            continue
        m = _NUMBER.match(text, i)
        if m and (c == "-" or c.isdigit()):
            end = m.end()
            if end < len(text) and (text[end].isalnum() or text[end] in "_."):
                raise UsageError(f"--where: bad number near {text[i:end + 1]!r}")
            toks.append(("number", m.group(0)))
            i = end
            continue
        m = _PATH.match(text, i)
        if m:
            word = m.group(0)
            if word.lower() in KEYWORDS:
                toks.append(("kw", word.lower()))
            else:
                toks.append(("path", word))
            i = m.end()
            continue
        raise UsageError(f"--where: unexpected character {c!r}")
    return toks


class _Parser:
    def __init__(self, toks, schema):
        self.toks = toks
        self.i = 0
        self.schema = schema

    def peek(self, kind=None, value=None):
        if self.i >= len(self.toks):
            return None
        t = self.toks[self.i]
        if kind and t[0] != kind:
            return None
        if value is not None and t[1] != value:
            return None
        return t

    def take(self, kind=None, value=None, what="token"):
        t = self.peek(kind, value)
        if t is None:
            got = self.toks[self.i][1] if self.i < len(self.toks) else "end of expression"
            raise UsageError(f"--where: expected {what}, got {got!r}")
        self.i += 1
        return t

    def parse(self):
        node = self.or_expr()
        if self.i != len(self.toks):
            raise UsageError(f"--where: unexpected {self.toks[self.i][1]!r}")
        return node

    def or_expr(self):
        node = self.and_expr()
        while self.peek("kw", "or"):
            self.i += 1
            node = ("or", node, self.and_expr())
        return node

    def and_expr(self):
        node = self.not_expr()
        while self.peek("kw", "and"):
            self.i += 1
            node = ("and", node, self.not_expr())
        return node

    def not_expr(self):
        if self.peek("kw", "not"):
            self.i += 1
            return ("not", self.not_expr())
        return self.primary()

    def primary(self):
        if self.peek("punct", "("):
            self.i += 1
            node = self.or_expr()
            self.take("punct", ")", "')'")
            return node
        return self.test()

    def literal(self):
        t = self.peek()
        if t and (t[0] in ("string", "number") or (t[0] == "kw" and t[1] in ("true", "false"))):
            self.i += 1
            return t
        raise UsageError(f"--where: expected a literal, got {t[1] if t else 'end of expression'!r}")

    def test(self):
        path = self.take("path", what="a field")[1]
        if not self.schema.has(path):
            raise UsageError(f"{self.schema.collection} has no field {path!r}")
        field = self.schema.field(path)
        if self.peek("kw", "is"):
            self.i += 1
            negate = bool(self.peek("kw", "not"))
            if negate:
                self.i += 1
            self.take("kw", "null", "null")
            return ("notnull" if negate else "isnull", field)
        negate = False
        if self.peek("kw", "not"):
            self.i += 1
            negate = True
            if not self.peek("kw", "in"):
                raise UsageError("--where: expected 'in' after 'not'")
        if self.peek("kw", "in"):
            self.i += 1
            self.take("punct", "(", "'('")
            values = [coerce(field, self.literal(), "=")]
            while self.peek("punct", ","):
                self.i += 1
                values.append(coerce(field, self.literal(), "="))
            self.take("punct", ")", "')'")
            return ("notin" if negate else "in", field, values)
        op = self.take("op", what="an operator")[1]
        return ("cmp", field, op, coerce(field, self.literal(), op))


def coerce(field, tok, op):
    kind, text = tok
    t = field.type
    if op == "~" and t != "string":
        raise UsageError(f"--where: '~' needs a string field; {field.name} is {t}")
    if t in ("int", "decimal"):
        if kind != "number":
            raise UsageError(f"--where: {field.name} is {t}; compare it with a number")
        return Decimal(text)
    if t == "string":
        if kind != "string":
            raise UsageError(f"--where: {field.name} is a string; compare it with a quoted string")
        return text
    if t == "bool":
        if kind != "kw":
            raise UsageError(f"--where: {field.name} is a bool; compare it with true or false")
        if op not in ("=", "!="):
            raise UsageError(f"--where: {field.name} is a bool; only = and != apply")
        return text == "true"
    if kind != "string":
        raise UsageError(f"--where: {field.name} is a {t}; compare it with a quoted {t}")
    try:
        if t == "date":
            return parse_date(text)
        try:
            return parse_datetime(text)
        except ValueError:
            d = parse_date(text)
            return datetime(d.year, d.month, d.day)
    except ValueError:
        raise UsageError(f"--where: {text!r} is not a valid {t}") from None


def parse_where(text: str | None, schema):
    if text is None:
        return None
    toks = tokenize(text)
    if not toks:
        raise UsageError("--where is empty")
    return _Parser(toks, schema).parse()


def evaluate(node, record) -> bool:
    """True when the record satisfies a node built by parse_where.

    Nodes: ("or", a, b), ("and", a, b), ("not", a), ("isnull", field),
    ("notnull", field), ("in", field, values), ("notin", field, values),
    ("cmp", field, op, literal). Literals are already typed by coerce.
    """
    raise NotImplementedError("export --where: evaluation is not written yet")
