"""Splits the text of a formula into tokens (formulas.md section 2)."""

import re
from dataclasses import dataclass

from .errors import FormulaError

NUMBER = r"(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?"
# Longer operators first, so that '<=' is not read as '<' followed by '='.
OPERATORS = ("<>", "<=", ">=", "+", "-", "*", "/", "^", "&", "=", "<", ">", "%", "(", ")", ",", ":")

_NUMBER = re.compile(NUMBER)
_REF = re.compile(r"\$?[A-Za-z]+\$?[0-9]+(?![A-Za-z0-9_(])")
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


@dataclass(frozen=True)
class Token:
    kind: str  # num, str, ref, name or op
    text: str


def _string(text: str, i: int) -> tuple[str, int]:
    """The value of the string literal that opens at text[i], and the index after it."""
    buf, j = [], i + 1
    while True:
        if j >= len(text):
            raise FormulaError("unterminated string")
        if text[j] == '"':
            if text[j + 1:j + 2] == '"':
                buf.append('"')
                j += 2
                continue
            return "".join(buf), j + 1
        buf.append(text[j])
        j += 1


def tokenize(text: str) -> list[Token]:
    out, i = [], 0
    while i < len(text):
        c = text[i]
        if c in " \t":
            i += 1
            continue
        if c == '"':
            value, i = _string(text, i)
            out.append(Token("str", value))
            continue
        if c.isdigit() or c == ".":
            m = _NUMBER.match(text, i)
            if not m:
                raise FormulaError(f"bad number at {i + 1}")
            out.append(Token("num", m.group()))
            i = m.end()
            continue
        m = _REF.match(text, i) or _NAME.match(text, i)
        if m:
            out.append(Token("ref" if m.re is _REF else "name", m.group()))
            i = m.end()
            continue
        for op in OPERATORS:
            if text.startswith(op, i):
                out.append(Token("op", op))
                i += len(op)
                break
        else:
            raise FormulaError(f"unexpected character {c!r} at {i + 1}")
    return out
