"""Values: numbers, text, booleans, empty cells and error values (values.md).

Numbers are always floats, so a bool is never taken for a number.
"""

import math
import re

from .tokens import NUMBER


class Error:
    __slots__ = ("code",)

    def __init__(self, code: str):
        self.code = code

    def __eq__(self, other) -> bool:
        return isinstance(other, Error) and other.code == self.code

    def __hash__(self) -> int:
        return hash(self.code)

    def __repr__(self) -> str:
        return self.code


DIV0 = Error("#DIV/0!")
VALUE = Error("#VALUE!")
REF = Error("#REF!")
NAME = Error("#NAME?")
NUM = Error("#NUM!")
CYCLE = Error("#CYCLE!")
PARSE = Error("#PARSE!")
CODES = tuple(e.code for e in (DIV0, VALUE, REF, NAME, NUM, CYCLE, PARSE))


class _Empty:
    def __repr__(self) -> str:
        return "EMPTY"


EMPTY = _Empty()

_NUMERIC_TEXT = re.compile(r"[ \t]*[+-]?" + NUMBER + r"[ \t]*")


def is_number(v) -> bool:
    return isinstance(v, float)


def parse_number(text: str) -> float | None:
    """The number a text holds (values.md 2.3), or None."""
    if not _NUMERIC_TEXT.fullmatch(text):
        return None
    n = float(text)
    return n if math.isfinite(n) else None


def number_text(x: float) -> str:
    """A number written as text (values.md 3.2)."""
    s = "%.10g" % x
    return "0" if s == "-0" else s


def to_number(v):
    if isinstance(v, (Error, float)):
        return v
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if v is EMPTY:
        return 0.0
    n = parse_number(v)
    return VALUE if n is None else n


def to_text(v):
    if isinstance(v, (Error, str)):
        return v
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if v is EMPTY:
        return ""
    return number_text(v)


def to_bool(v):
    if isinstance(v, (Error, bool)):
        return v
    if isinstance(v, float):
        return v != 0
    if v is EMPTY:
        return False
    if v.upper() in ("TRUE", "FALSE"):
        return v.upper() == "TRUE"
    return VALUE


def _rank(v) -> int:
    return 0 if isinstance(v, float) else 2 if isinstance(v, bool) else 1


def _blank_like(v):
    return 0.0 if isinstance(v, float) else False if isinstance(v, bool) else ""


def compare(op: str, a, b):
    """A comparison (values.md section 4)."""
    if isinstance(a, Error):
        return a
    if isinstance(b, Error):
        return b
    if a is EMPTY and b is EMPTY:
        a = b = 0.0
    elif a is EMPTY:
        a = _blank_like(b)
    elif b is EMPTY:
        b = _blank_like(a)
    if _rank(a) != _rank(b):
        x, y = _rank(a), _rank(b)
    elif isinstance(a, str):
        x, y = a.lower(), b.lower()
    else:
        x, y = a, b
    if op == "=":
        return x == y
    if op == "<>":
        return x != y
    if op == "<":
        return x < y
    if op == ">":
        return x > y
    if op == "<=":
        return x <= y
    return x >= y
