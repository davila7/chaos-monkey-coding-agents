"""Evaluates the cells of a sheet (values.md sections 5 and 6, functions.md section 1)."""

import math
import sys

from .errors import FormulaError
from .functions import FUNCTIONS, STRICT
from .parser import parse, references
from .sheets import Sheet
from .values import CYCLE, DIV0, EMPTY, NAME, NUM, PARSE, REF, VALUE, Error, compare, to_number, to_text

COMPARISONS = ("=", "<>", "<", ">", "<=", ">=")

sys.setrecursionlimit(max(sys.getrecursionlimit(), 20000))


class Arg:
    """One argument of a function call (functions.md 1.2)."""

    def __init__(self, ev: "Evaluator", node):
        self.ev = ev
        self.node = node
        self.is_ref = node[0] in ("ref", "range")
        self._value = None

    def value(self):
        if self._value is None:
            self._value = self.ev.eval(self.node)
        return self._value

    def cells(self) -> list:
        kind, target = self.node
        if not target.valid:
            return [REF]
        if kind == "ref":
            return [self.ev.read(target.name)]
        return [self.ev.read(name) for name in self.ev.sheet.names_in(target)]


def _power(x: float, y: float):
    if x == 0 and y < 0:
        return DIV0
    if x < 0 and y != int(y):
        return NUM
    try:
        return math.pow(x, y)
    except OverflowError:
        return NUM


def cycle_cells(deps: dict[str, set[str]]) -> set[str]:
    """Cells that belong to a cycle of references (values.md 6.1): Tarjan's components."""
    index, low, stack, on_stack, out = {}, {}, [], set(), set()

    def visit(v):
        index[v] = low[v] = len(index)
        stack.append(v)
        on_stack.add(v)
        for w in deps.get(v, ()):
            if w not in index:
                visit(w)
                low[v] = min(low[v], low[w])
            elif w in on_stack:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp = []
            while True:
                w = stack.pop()
                on_stack.discard(w)
                comp.append(w)
                if w == v:
                    break
            if len(comp) > 1 or v in deps.get(v, ()):
                out.update(comp)

    for v in sorted(deps):
        if v not in index:
            visit(v)
    return out


class Evaluator:
    def __init__(self, sheet: Sheet):
        self.sheet = sheet
        self.trees = {}
        for name, cell in sheet.cells.items():
            if cell.formula is not None:
                try:
                    self.trees[name] = parse(cell.formula[1:])
                except FormulaError:
                    self.trees[name] = None
        self.values = {name: CYCLE for name in cycle_cells(self.dependencies())}

    def dependencies(self) -> dict[str, set[str]]:
        """The cells of the sheet each formula names, whether or not evaluating it reads them."""
        deps = {}
        for name, tree in self.trees.items():
            found = set()
            for kind, target in (references(tree) if tree is not None else ()):
                if not target.valid:
                    continue
                if kind == "ref":
                    if target.name in self.sheet.cells:
                        found.add(target.name)
                else:
                    found.update(self.sheet.names_in(target))
            deps[name] = found
        return deps

    def read(self, name: str):
        """The value of a cell as a reference reads it."""
        if name not in self.sheet.cells:
            return EMPTY
        return self.value_of(name)

    def value_of(self, name: str):
        """The value of a cell of the sheet (values.md section 5)."""
        if name in self.values:
            return self.values[name]
        cell = self.sheet.cells[name]
        if cell.formula is None:
            v = cell.literal
        else:
            tree = self.trees[name]
            v = PARSE if tree is None else self.eval(tree)
            if v is EMPTY or v == 0 and isinstance(v, float):
                v = 0.0
        self.values[name] = v
        return v

    def eval(self, node):
        kind = node[0]
        if kind == "num":
            return node[1] if math.isfinite(node[1]) else NUM
        if kind in ("str", "bool"):
            return node[1]
        if kind == "name":
            return NAME
        if kind == "ref":
            return self.read(node[1].name) if node[1].valid else REF
        if kind == "range":
            return VALUE if node[1].valid else REF
        if kind in ("neg", "pos", "pct"):
            n = to_number(self.eval(node[1]))
            if isinstance(n, Error):
                return n
            return -n if kind == "neg" else n / 100 if kind == "pct" else n
        if kind == "bin":
            return self.binary(node[1], self.eval(node[2]), self.eval(node[3]))
        return self.call(node[1], node[2])

    def binary(self, op: str, a, b):
        if op == "&":
            x, y = to_text(a), to_text(b)
        elif op in COMPARISONS:
            return compare(op, a, b)
        else:
            x, y = to_number(a), to_number(b)
        if isinstance(x, Error):
            return x
        if isinstance(y, Error):
            return y
        if op == "&":
            return x + y
        if op == "+":
            r = x + y
        elif op == "-":
            r = x - y
        elif op == "*":
            r = x * y
        elif op == "/":
            if y == 0:
                return DIV0
            r = x / y
        else:
            r = _power(x, y)
        return r if isinstance(r, Error) or math.isfinite(r) else NUM

    def call(self, name: str, nodes: list):
        entry = FUNCTIONS.get(name)
        if entry is None:
            return NAME
        fn, treatment, fewest, most = entry
        if len(nodes) < fewest or (most is not None and len(nodes) > most):
            return VALUE
        args = [Arg(self, n) for n in nodes]
        if treatment == STRICT:
            for a in args:
                if not a.is_ref and isinstance(a.value(), Error):
                    return a.value()
        return fn(args)
