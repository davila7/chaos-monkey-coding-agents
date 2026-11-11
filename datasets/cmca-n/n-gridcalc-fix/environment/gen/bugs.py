"""Edits that turn the package sources under src/ into the tree shipped in /app.

Each entry is (id, file under gridcalc/, text in src, text shipped); an id may
have more than one entry. The ids group them: V entries fail the shipped unit
tests, R entries pass them and show in tools/check.py, X entries pass both and
the visible data exercises each on exactly one sheet (build.py checks it);
held-out data exercises them often.
"""

from pathlib import Path

BUGS = [
    # A number literal has no exponent, so '1.5e3' is the number 1.5 followed by a reference E3.
    ("V1", "tokens.py",
     'NUMBER = r"(?:[0-9]+(?:\\.[0-9]*)?|\\.[0-9]+)(?:[eE][+-]?[0-9]+)?"\n',
     'NUMBER = r"(?:[0-9]+(?:\\.[0-9]*)?|\\.[0-9]+)"\n'),
    # '^' groups to the left: 2^3^2 is 64.
    ("V2", "parser.py",
     '    "^": (60, 60),\n',
     '    "^": (60, 61),\n'),
    # Column names are read as plain base 26 from A = 0, so AA is column 1.
    ("V3", "refs.py",
     "        n = n * 26 + (ord(c) - 64)\n    return n\n",
     "        n = n * 26 + (ord(c) - 65)\n    return n + 1\n"),
    # Numbers become text with str(), so 1/3 is '0.3333333333333333'.
    ("V4", "values.py",
     '    s = "%.10g" % x\n    return "0" if s == "-0" else s\n',
     "    if x == int(x):\n        return str(int(x))\n    return str(x)\n"),
    # Cells are listed in code point order of their names: A10 before A2, AA1 before B1.
    ("R1", "report.py",
     "from .refs import cell_key\n",
     ""),
    ("R1", "report.py",
     "    for name in sorted(sheet.cells, key=cell_key):\n",
     "    for name in sorted(sheet.cells):\n"),
    # A bool passes the number test first and is typed "number".
    ("R2", "report.py",
     '    if isinstance(v, bool):\n        return "bool"\n    if isinstance(v, float):\n        return "number"\n',
     '    if isinstance(v, (int, float)):\n        return "number"\n    if isinstance(v, bool):\n        return "bool"\n'),
    # A cell named twice is listed twice.
    ("R3", "parser.py",
     "    return sorted(set(names), key=ref_key)\n",
     "    return sorted(names, key=ref_key)\n"),
    # A prefix minus binds tighter than '^': -2^2 is 4.
    ("X1", "parser.py",
     "PREFIX = 50\n",
     "PREFIX = 65\n"),
    # Text that holds a number counts as a number inside references.
    ("X2", "functions.py",
     "                if isinstance(v, Error):\n                    return v\n                if is_number(v):\n                    out.append(v)\n        else:\n            n = to_number(a.value())\n",
     "                if isinstance(v, Error):\n                    return v\n                if isinstance(v, str):\n                    v = to_number(v)\n                if is_number(v):\n                    out.append(v)\n        else:\n            n = to_number(a.value())\n"),
    # A range only holds cells when its first corner is the top left one.
    ("X3", "refs.py",
     "    def contains(self, col: int, row: int) -> bool:\n        c1, r1, c2, r2 = self.bounds()\n        return c1 <= col <= c2 and r1 <= row <= r2\n",
     "    def contains(self, col: int, row: int) -> bool:\n        return self.a.col <= col <= self.b.col and self.a.row <= row <= self.b.row\n"),
    # IF evaluates every argument first, so an error in the branch not taken is the result.
    ("X4", "functions.py",
     '    "IF": (fn_if, LAZY, 2, 3),\n',
     '    "IF": (fn_if, STRICT, 2, 3),\n'),
    # A cell the sheet does not define reads as the number 0, not as an empty cell.
    ("X5", "evaluate.py",
     "        if name not in self.sheet.cells:\n            return EMPTY\n",
     "        if name not in self.sheet.cells:\n            return 0.0\n"),
]


def apply(package_dir: Path, ids) -> None:
    """Applies the named bugs to a copy of the gridcalc package in place."""
    for bug_id, rel, good, bad in BUGS:
        if bug_id not in ids:
            continue
        p = Path(package_dir) / rel
        text = p.read_text(encoding="utf-8")
        if text.count(good) != 1:
            raise SystemExit(f"{bug_id} {rel}: expected one match")
        p.write_text(text.replace(good, bad, 1), encoding="utf-8")


ALL = sorted({b[0] for b in BUGS})
