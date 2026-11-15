"""Generates a data directory of sheet files.

generate(root, seed, sheets=120, held_out=False) writes root/sheets/<id>.sheet.

Five features exercise rules the visible tests do not reach: a prefix minus
before '^' (neg_pow), text that holds a number inside an aggregated range
(numeric_text), ranges written from another corner than the top left one
(reversed), an IF whose branch not taken is an error (if_branch) and
references to cells the sheet does not define in text, count or comparison
contexts (empty_ref). The visible data set carries each feature on exactly one
sheet and nowhere else; the held-out data set carries them often.
"""

import random
from pathlib import Path

FEATURES = ("neg_pow", "numeric_text", "reversed", "if_branch", "empty_ref")
WORDS = ["apple", "Birch", "cedar", "delta", "Ember", "fjord", "gamma", "Heron", "iris", "Juniper",
         "kelp", "Lumen", "maple", "Nectar", "olive", "Pepper", "quartz", "Raven", "sage", "Tundra"]


def col_letters(n: int) -> str:
    out = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        out = chr(65 + r) + out
    return out


def name(col: int, row: int) -> str:
    return f"{col_letters(col)}{row}"


def number_literal(rng: random.Random, zeros: float) -> tuple[str, float]:
    x = rng.random()
    if x < zeros:
        return "0", 0.0
    if x < 0.55:
        n = rng.randint(1, 250)
        return str(n), float(n)
    if x < 0.75:
        v = rng.randint(1, 4000) / 100
        return f"{v:g}", v
    if x < 0.85:
        n = -rng.randint(1, 60)
        return str(n), float(n)
    if x < 0.93:
        m, e = rng.randint(11, 95) / 10, rng.randint(1, 3)
        text = f"{m:g}{rng.choice('eE')}{e}"
        return text, float(text)
    v = rng.randint(1, 99) / 1000
    return f"{v:g}", v


class Builder:
    def __init__(self, rng: random.Random, feats: set[str], held_out: bool):
        self.rng = rng
        self.feats = feats
        self.held_out = held_out
        self.lines: list[str] = []
        self.kind: dict[str, str] = {}
        self.value: dict[str, float] = {}
        self.formulas: list[str] = []
        # Per-sheet traits: bool values, cells named twice in one formula, a tall or a wide block.
        self.bools = rng.random() < (0.6 if held_out else 0.35)
        self.dups = rng.random() < (0.6 if held_out else 0.3)
        self.tall = rng.random() < (0.4 if held_out else 0.2)
        self.wide = rng.random() < (0.35 if held_out else 0.12)

    def block(self) -> None:
        rng = self.rng
        self.c0 = 25 if self.wide else 1
        self.ncols = rng.randint(2, 4)
        self.nrows = rng.randint(10, 14) if self.tall else rng.randint(3, 9)
        zeros = 0.12 if self.held_out else 0.04
        for c in range(self.c0, self.c0 + self.ncols):
            for r in range(1, self.nrows + 1):
                if rng.random() < 0.08:
                    continue
                x = rng.random()
                if "numeric_text" in self.feats and x < 0.15:
                    content, kind = f"'{rng.randint(1, 99)}", "numtext"
                elif x < 0.64:
                    content, v = number_literal(rng, zeros)
                    kind = "num"
                    self.value[name(c, r)] = v
                elif x < 0.80:
                    content, kind = rng.choice(WORDS), "word"
                elif x < 0.88 and self.bools:
                    content, kind = rng.choice(["TRUE", "FALSE", "true", "False"]), "bool"
                else:
                    content, kind = "'" + rng.choice(WORDS) + rng.choice(["", " 2", "-x"]), "word"
                self.put(name(c, r), content, kind)

    def put(self, cell: str, content: str, kind: str) -> None:
        self.kind[cell] = kind
        self.lines.append(f"{cell}: {content}")

    def pick(self, kind: str, nonzero: bool = False) -> str | None:
        names = [n for n, k in self.kind.items() if k == kind and (not nonzero or self.value.get(n, 0) != 0)]
        return self.rng.choice(names) if names else None

    def num(self, nonzero: bool = False) -> str:
        return self.pick("num", nonzero) or self.constant()

    def constant(self) -> str:
        return str(self.rng.randint(2, 9))

    def style(self, cell: str) -> str:
        x = self.rng.random()
        if x < 0.06:
            return "$" + cell.rstrip("0123456789") + "$" + cell.lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        if x < 0.1:
            return cell.lower()
        return cell

    def area(self, reversed_ok: bool) -> str:
        rng = self.rng
        c1 = rng.randint(self.c0, self.c0 + self.ncols - 1)
        c2 = rng.randint(c1, self.c0 + self.ncols - 1)
        r1 = rng.randint(1, self.nrows)
        r2 = rng.randint(r1, self.nrows)
        a, b = (c1, r1), (c2, r2)
        if reversed_ok and (a != b) and rng.random() < 0.5:
            a, b = rng.choice([(b, a), ((c1, r2), (c2, r1)), ((c2, r1), (c1, r2))])
        return f"{self.style(name(*a))}:{self.style(name(*b))}"

    def undefined(self) -> str:
        rng = self.rng
        holes = [name(c, r) for c in range(self.c0, self.c0 + self.ncols) for r in range(1, self.nrows + 1) if name(c, r) not in self.kind]
        if holes and rng.random() < 0.5:
            return rng.choice(holes)
        return name(rng.randint(self.c0, self.c0 + self.ncols), self.nrows + rng.randint(1, 6))

    def formula(self) -> str:
        rng = self.rng
        a, b, k = self.num(), self.num(), self.constant()
        if a == b and not self.dups:
            b = self.constant()
        a, b = self.style(a), self.style(b)
        w = self.pick("word")
        w = self.style(w) if w else '"plain"'
        bo = self.pick("bool")
        bo = self.style(bo) if bo else "TRUE"
        rev = "reversed" in self.feats
        cats = ["arith", "power", "agg", "agg", "text", "if", "iferror", "error", "round"]
        if self.bools:
            cats.append("compare")
        if self.dups:
            cats.append("dup")
        if self.formulas:
            cats.append("chain")
        # FEATURES fixes the order; iterating the set would depend on string hashing.
        cats += [f for f in FEATURES if f in self.feats and f not in ("numeric_text", "reversed")]
        cat = rng.choice(cats)
        if cat == "arith":
            return rng.choice([f"={a}+{b}*{k}", f"=({a}-{b})/{k}", f"={a}*{b}-{k}", f"={a}/{b}", f"={a}%*{k}", f"=-{a}*{k}", f"={a}*-{k}+{b}"])
        if cat == "power":
            return rng.choice([f"={a}^2", f"=({a}+{b})^2", f"={rng.randint(2, 3)}^{rng.randint(2, 3)}^2", f"={a}^0.5", f"={k}^-1", f"={a}^2^0.5"])
        if cat == "agg":
            fn = rng.choice(["SUM", "AVERAGE", "MIN", "MAX", "COUNT", "sum"])
            if rng.random() < 0.25:
                return f"={fn}({self.area(rev)}, {a}, {k})"
            return f"={fn}({self.area(rev)})"
        if cat == "text":
            return rng.choice([f'="n"&{a}', f'=CONCAT("id-", {a}, "/", {w})', f"=LEN({w})", f'="r"&{a}/{rng.choice([3, 7, 9])}',
                               f'=CONCAT("c", {self.area(rev)})', f'="v"&{a}*{b}'])
        if cat == "compare":
            word = rng.choice(WORDS)
            return rng.choice([f"={a}>{b}", f'={w}="{rng.choice([word, word.upper(), word.lower()])}"', f"=AND({a}>0, {b}<{k})",
                               f"=NOT({bo})", f"=OR({self.area(rev)})", f"={a}<>{b}", f'={w}<"m"'])
        if cat == "if":
            if not self.dups:
                return rng.choice([f'=IF({a}>{k}, "big", "small")', f"=IF({a}<{b}, {k}, -{k})"])
            return rng.choice([f"=IF({a}>{b}, {a}, {b})", f'=IF({a}>{k}, "big", "small")', f"=IF({bo}, {a}*2, {b}+1)",
                               f"=IF({a}>{b}, {a}-{b}, 0)", f"=if({a}<{k}, {a}, {k})"] + ([f"=IF({a}>{b}, {a}-{b})"] if self.bools else []))
        if cat == "iferror":
            return rng.choice([f"=IFERROR({a}/{b}, 0)", f'=IFERROR({a}+{w}, "n/a")', f"=IFERROR(SUMM({a}), -1)"])
        if cat == "error":
            return rng.choice([f"=SUMM({a})", f"={a}+{w}", "=ZZZ1*2", f"={a}*(", f"={self.area(False)}+1", "=(-8)^0.5", f"={a}/0", f"=ROUND({a}, 40)"])
        if cat == "round":
            return rng.choice([f"=ROUND({a}/7, 2)", f"=ROUND({a}*1.5, 0)", f"=ABS({a}-{b})", f"=ROUND({a}, -1)", f"=ROUND({a}/8, 1)"])
        if cat == "dup":
            return rng.choice([f"={a}*{a}+{b}", f"=SUM({a}, {a})", f"=IF({a}>{k}, {a}, -{a})"])
        if cat == "chain":
            f = self.style(rng.choice(self.formulas))
            return rng.choice([f"={f}+{a}", f"=IFERROR({f}*2, -1)", f'=CONCAT({f}, "!")'])
        return self.feature(cat)

    def feature(self, feat: str) -> str:
        """A formula that exercises a feature. Each one changes its cell's value whenever the rule it covers is broken."""
        rng = self.rng
        if feat == "neg_pow":
            a = self.style(self.num(nonzero=True))
            return rng.choice([f"=-{a}^2", f"=-{rng.randint(2, 9)}^2+{a}", f"={a}*-{rng.randint(2, 5)}^2", f"=-({a}+1)^2"])
        if feat == "numeric_text":
            fn = rng.choice(["SUM", "COUNT", "MAX", "AVERAGE"])
            return f"={fn}({name(self.c0, 1)}:{name(self.c0 + self.ncols - 1, self.nrows)})"
        if feat == "reversed":
            fn = rng.choice(["SUM", "COUNT", "CONCAT"])
            return f"={fn}({name(self.c0 + self.ncols - 1, self.nrows)}:{name(self.c0, 1)})"
        if feat == "if_branch":
            z = self.pick("num")
            if z is None or self.value[z] != 0:
                z = self.zero()
            a = self.style(self.num())
            return rng.choice([f"=IF({z}=0, 0, {a}/{z})", f"=IF({z}<>0, {a}/{z}, -1)", f'=IF({z}=0, "none", {a}/{z})'])
        u = self.undefined()
        a = self.style(self.num())
        options = [f'={u}&"-x"', f"=COUNT({u}, {a})", f"=LEN({u})", f'={u}=""', f"=AVERAGE({u}, {a}, 5)", f'=CONCAT("[", {u}, "]")']
        if self.held_out:
            # These two read an undefined cell as a number, which 0 gets right and "" gets wrong.
            options += [f"={u}=0", f"={u}+{a}"]
        return rng.choice(options)

    def zero(self) -> str:
        """A cell holding 0, added next to the block."""
        cell = name(self.c0, self.nrows + 1)
        if cell not in self.kind:
            self.put(cell, "0", "num")
            self.value[cell] = 0.0
        return cell

    def numeric_text_cell(self) -> None:
        cell = name(self.c0, 1)
        self.lines = [ln for ln in self.lines if not ln.startswith(cell + ":")]
        self.kind[cell] = "numtext"
        self.value.pop(cell, None)
        self.lines.insert(0, f"{cell}: '{self.rng.randint(10, 99)}")

    def sheet(self, forced: str | None) -> str:
        rng = self.rng
        self.block()
        fcol = self.c0 + self.ncols + 1
        count = rng.randint(6, 16) if self.held_out else rng.randint(4, 12)
        texts = []
        if forced == "numeric_text":
            self.numeric_text_cell()
        if forced:
            texts.append(self.feature(forced))
        while len(texts) < count:
            texts.append(self.formula())
            self.formulas.append(name(fcol + (len(texts) - 1) // 8, (len(texts) - 1) % 8 + 1))
        for i, text in enumerate(texts):
            self.put(name(fcol + i // 8, i % 8 + 1), text, "formula")
        if rng.random() < (0.08 if self.held_out else 0.05):
            x, y = name(fcol + 2, 1), name(fcol + 2, 2)
            self.put(x, f"={y}+1", "formula")
            self.put(y, f"={x}*2", "formula")
        body = list(self.lines)
        if self.held_out and rng.random() < 0.3:
            rng.shuffle(body)
        return "# sheet\n" + "\n".join(body) + "\n"


def broken(rng: random.Random, text: str) -> str:
    lines = text.split("\n")
    i = rng.randint(1, len(lines) - 2)
    cell = lines[i].split(":", 1)[0]
    bad = rng.choice([f"{cell} = 4", lines[i], "A0: 3", f"{cell}:", "AAA1: 5", "B 2: 7"])
    lines.insert(i + 1, bad)
    return "\n".join(lines)


def generate(root: Path, seed: int, sheets: int = 120, held_out: bool = False) -> None:
    rng = random.Random(seed)
    out = Path(root) / "sheets"
    out.mkdir(parents=True, exist_ok=True)
    planted = {} if held_out else dict(zip(rng.sample(range(sheets), len(FEATURES)), FEATURES))
    for i in range(sheets):
        if held_out:
            feats = {f for f in FEATURES if rng.random() < 0.35}
            forced = None
        else:
            forced = planted.get(i)
            feats = {forced} if forced else set()
        text = Builder(rng, feats, held_out).sheet(forced)
        if forced is None and rng.random() < 0.07:
            text = broken(rng, text)
        (out / f"s-{i + 1:03d}.sheet").write_text(text, encoding="utf-8")
