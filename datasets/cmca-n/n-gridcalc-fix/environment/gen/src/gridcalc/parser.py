"""Reads the tokens of a formula into an expression tree (formulas.md section 3).

Nodes are tuples: ("num", float), ("str", text), ("bool", flag), ("name", text),
("ref", Ref), ("range", Range), ("neg", node), ("pos", node), ("pct", node),
("bin", operator, left, right) and ("call", NAME, [argument nodes]).
"""

from .errors import FormulaError
from .refs import Range, ref_key, parse_ref
from .tokens import Token, tokenize

# Binding power (left, right) of each infix operator. A right power above the
# left one groups to the left; an equal one groups to the right.
INFIX = {
    "=": (10, 11), "<>": (10, 11), "<": (10, 11), ">": (10, 11), "<=": (10, 11), ">=": (10, 11),
    "&": (20, 21),
    "+": (30, 31), "-": (30, 31),
    "*": (40, 41), "/": (40, 41),
    "^": (60, 60),
}
PREFIX = 50
POSTFIX = 70


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.i = 0

    def peek(self) -> Token | None:
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def at(self, op: str) -> bool:
        t = self.peek()
        return t is not None and t.kind == "op" and t.text == op

    def next(self) -> Token:
        t = self.peek()
        if t is None:
            raise FormulaError("unexpected end of formula")
        self.i += 1
        return t

    def expect(self, op: str) -> None:
        if not self.at(op):
            raise FormulaError(f"expected {op!r}")
        self.i += 1

    def expr(self, min_bp: int):
        left = self.prefix()
        while (t := self.peek()) is not None and t.kind == "op":
            if t.text == "%":
                if POSTFIX < min_bp:
                    break
                self.i += 1
                left = ("pct", left)
                continue
            if t.text not in INFIX:
                break
            lbp, rbp = INFIX[t.text]
            if lbp < min_bp:
                break
            self.i += 1
            left = ("bin", t.text, left, self.expr(rbp))
        return left

    def prefix(self):
        t = self.next()
        if t.kind == "op" and t.text in ("-", "+"):
            return ("neg" if t.text == "-" else "pos", self.expr(PREFIX))
        if t.kind == "op" and t.text == "(":
            inner = self.expr(0)
            self.expect(")")
            return inner
        if t.kind == "num":
            return ("num", float(t.text))
        if t.kind == "str":
            return ("str", t.text)
        if t.kind == "ref":
            first = parse_ref(t.text)
            if not self.at(":"):
                return ("ref", first)
            self.i += 1
            second = self.next()
            if second.kind != "ref":
                raise FormulaError("a range needs a cell on both sides of ':'")
            return ("range", Range(first, parse_ref(second.text)))
        if t.kind == "name":
            if self.at("("):
                self.i += 1
                return ("call", t.text.upper(), self.arguments())
            if t.text.upper() in ("TRUE", "FALSE"):
                return ("bool", t.text.upper() == "TRUE")
            return ("name", t.text)
        raise FormulaError(f"unexpected {t.text!r}")

    def arguments(self) -> list:
        args = []
        if not self.at(")"):
            args.append(self.expr(0))
            while self.at(","):
                self.i += 1
                args.append(self.expr(0))
        self.expect(")")
        return args


def parse(text: str):
    """The expression tree of a formula, given its text after the leading '='."""
    p = Parser(tokenize(text))
    tree = p.expr(0)
    if p.peek() is not None:
        raise FormulaError(f"unexpected {p.peek().text!r}")
    return tree


def references(tree):
    """Every ref and range node of a tree, in the order they are written."""
    kind = tree[0]
    if kind in ("ref", "range"):
        yield tree
    elif kind in ("neg", "pos", "pct"):
        yield from references(tree[1])
    elif kind == "bin":
        yield from references(tree[2])
        yield from references(tree[3])
    elif kind == "call":
        for arg in tree[2]:
            yield from references(arg)


def ref_names(tree) -> list[str]:
    """The refs listing of a formula (output.md 2.5)."""
    names = [node[1].name for node in references(tree) if node[1].valid]
    return sorted(set(names), key=ref_key)
