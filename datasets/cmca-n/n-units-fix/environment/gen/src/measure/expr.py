"""Unit expressions such as km/h, kg*m/s^2 or W/(m^2*K) (units.md section 4)."""

import re
from dataclasses import dataclass
from fractions import Fraction

from .dims import Dimension
from .errors import ParseError
from .table import Table, Unit

TOKEN = re.compile(r"[A-Za-z_]+|\d+|[*/^()-]")


@dataclass(frozen=True)
class Term:
    scale: Fraction
    unit: Unit
    exp: int


@dataclass(frozen=True)
class UnitExpr:
    text: str
    terms: tuple[Term, ...]
    factor: Fraction
    dim: Dimension
    kind: str
    offset: Fraction | None


def tokenize(text: str) -> list[str]:
    out, pos = [], 0
    while pos < len(text):
        m = TOKEN.match(text, pos)
        if not m:
            raise ParseError(f"unit {text!r}: unexpected character {text[pos]!r}")
        out.append(m.group())
        pos = m.end()
    return out


class _Parser:
    def __init__(self, text: str, table: Table):
        self.text = text
        self.table = table
        self.toks = tokenize(text)
        self.i = 0

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else None

    def take(self):
        tok = self.peek()
        self.i += 1
        return tok

    def fail(self, why: str):
        raise ParseError(f"unit {self.text!r}: {why}")

    def group(self) -> list[Term]:
        terms = self.term()
        sign = 1
        while self.peek() in ("*", "/"):
            if self.take() == "/":
                if sign < 0:
                    self.fail("a second '/' in one group")
                sign = -1
            terms += [Term(t.scale, t.unit, t.exp * sign) for t in self.term()]
        return terms

    def term(self) -> list[Term]:
        tok = self.take()
        if tok is None:
            self.fail("ends where a unit is expected")
        if tok == "(":
            terms = self.group()
            if self.take() != ")":
                self.fail("missing ')'")
        elif tok == "1":
            terms = []
        elif tok[0].isalpha() or tok[0] == "_":
            scale, unit = self.table.lookup(tok)
            terms = [Term(scale, unit, 1)]
        else:
            self.fail(f"unexpected {tok!r}")
        if self.peek() == "^":
            self.take()
            n = self.exponent()
            terms = [Term(t.scale, t.unit, t.exp * n) for t in terms]
        return terms

    def exponent(self) -> int:
        negative = self.peek() == "-"
        if negative:
            self.take()
        tok = self.take()
        if tok is None or not tok.isdigit():
            self.fail("an exponent is a whole number")
        n = int(tok)
        if n == 0:
            self.fail("an exponent cannot be 0")
        return -n if negative else n


def _resolve(text: str, terms: tuple[Term, ...]) -> UnitExpr:
    factor, dim = Fraction(1), Dimension()
    for t in terms:
        factor *= (t.scale * t.unit.factor) ** t.exp
        dim = dim * t.unit.dim ** t.exp
    kind, offset = "plain", None
    single = terms[0] if len(terms) == 1 and terms[0].exp == 1 else None
    if single is not None and single.unit.affine:
        kind, offset = "absolute", single.unit.offset
    elif single is not None and single.unit.delta:
        kind = "difference"
    return UnitExpr(text, terms, factor, dim, kind, offset)


def parse_unit(text: str, table: Table) -> UnitExpr:
    if not isinstance(text, str) or not text:
        raise ParseError("empty unit")
    p = _Parser(text, table)
    terms = p.group()
    if p.peek() is not None:
        p.fail(f"unexpected {p.peek()!r}")
    return _resolve(text, tuple(terms))
