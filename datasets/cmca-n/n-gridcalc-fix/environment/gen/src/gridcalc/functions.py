"""The functions a formula can call (functions.md).

Each function takes a list of arguments. An argument has `is_ref` (it is
written as a reference or a range), `value()` (its value, evaluated on first
use) and, for a reference, `cells()` (the values of the cells it names, in
cell order).
"""

import math
from decimal import ROUND_HALF_UP, Decimal

from .values import DIV0, EMPTY, VALUE, Error, is_number, to_bool, to_number, to_text

# How the evaluator treats the arguments before calling (functions.md 1.3).
STRICT = "strict"
TOLERANT = "tolerant"
LAZY = "lazy"


def _numbers(args):
    """The numbers a list of arguments contributes (functions.md 2.1), or the first error value."""
    out = []
    for a in args:
        if a.is_ref:
            for v in a.cells():
                if isinstance(v, Error):
                    return v
                if is_number(v):
                    out.append(v)
        else:
            n = to_number(a.value())
            if isinstance(n, Error):
                return n
            out.append(n)
    return out


def fn_sum(args):
    ns = _numbers(args)
    return ns if isinstance(ns, Error) else math.fsum(ns)


def fn_average(args):
    ns = _numbers(args)
    if isinstance(ns, Error):
        return ns
    return math.fsum(ns) / len(ns) if ns else DIV0


def fn_min(args):
    ns = _numbers(args)
    return ns if isinstance(ns, Error) else min(ns, default=0.0)


def fn_max(args):
    ns = _numbers(args)
    return ns if isinstance(ns, Error) else max(ns, default=0.0)


def fn_count(args):
    n = 0
    for a in args:
        if a.is_ref:
            n += sum(1 for v in a.cells() if is_number(v))
            continue
        v = a.value()
        if isinstance(v, Error) or v is EMPTY:
            continue
        if not isinstance(to_number(v), Error):
            n += 1
    return float(n)


def fn_round(args):
    x = to_number(args[0].value())
    d = to_number(args[1].value()) if len(args) > 1 else 0.0
    if isinstance(x, Error):
        return x
    if isinstance(d, Error):
        return d
    d = int(d)
    if not -10 <= d <= 10:
        return VALUE
    # repr gives the shortest decimal that reads back as x, so 2.675 rounds to 2.68.
    q = Decimal(repr(x)).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP)
    return float(q)


def fn_abs(args):
    x = to_number(args[0].value())
    return x if isinstance(x, Error) else abs(x)


def fn_concat(args):
    parts = []
    for a in args:
        for v in (a.cells() if a.is_ref else [a.value()]):
            t = to_text(v)
            if isinstance(t, Error):
                return t
            parts.append(t)
    return "".join(parts)


def fn_len(args):
    t = to_text(args[0].value())
    return t if isinstance(t, Error) else float(len(t))


def _flags(args):
    out = []
    for a in args:
        if a.is_ref:
            for v in a.cells():
                if isinstance(v, Error):
                    return v
                if isinstance(v, bool) or is_number(v):
                    out.append(to_bool(v))
        else:
            b = to_bool(a.value())
            if isinstance(b, Error):
                return b
            out.append(b)
    return out


def fn_and(args):
    flags = _flags(args)
    if isinstance(flags, Error):
        return flags
    return all(flags) if flags else VALUE


def fn_or(args):
    flags = _flags(args)
    if isinstance(flags, Error):
        return flags
    return any(flags) if flags else VALUE


def fn_not(args):
    b = to_bool(args[0].value())
    return b if isinstance(b, Error) else not b


def fn_if(args):
    c = to_bool(args[0].value())
    if isinstance(c, Error):
        return c
    if c:
        return args[1].value()
    return args[2].value() if len(args) > 2 else False


def fn_iferror(args):
    v = args[0].value()
    return args[1].value() if isinstance(v, Error) else v


# name: (function, treatment, fewest arguments, most arguments or None)
FUNCTIONS = {
    "SUM": (fn_sum, STRICT, 1, None),
    "AVERAGE": (fn_average, STRICT, 1, None),
    "MIN": (fn_min, STRICT, 1, None),
    "MAX": (fn_max, STRICT, 1, None),
    "COUNT": (fn_count, TOLERANT, 1, None),
    "ROUND": (fn_round, STRICT, 1, 2),
    "ABS": (fn_abs, STRICT, 1, 1),
    "CONCAT": (fn_concat, STRICT, 1, None),
    "LEN": (fn_len, STRICT, 1, 1),
    "AND": (fn_and, STRICT, 1, None),
    "OR": (fn_or, STRICT, 1, None),
    "NOT": (fn_not, STRICT, 1, 1),
    "IF": (fn_if, LAZY, 2, 3),
    "IFERROR": (fn_iferror, LAZY, 2, 2),
}
