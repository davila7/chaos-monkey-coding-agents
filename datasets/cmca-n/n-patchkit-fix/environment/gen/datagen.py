"""Writes a data directory for the patchkit package: one case file per case under cases/.

The output depends only on the seed and the keyword arguments. The visible data
(build.py) and the held-out data (tests/verify.py) come from this one file.
"""

import json
import random
from difflib import SequenceMatcher
from pathlib import Path

WORDS = ["alpha", "bravo", "cache", "delta", "entry", "field", "gauge", "handle", "index", "joint", "kernel", "ledger",
         "mount", "node", "offset", "parcel", "query", "relay", "socket", "token", "update", "vector", "widget", "yield",
         "zone", "batch", "cursor", "digest", "event", "filter", "group", "header", "input", "label", "metric", "notice",
         "order", "packet", "quota", "range", "signal", "table", "unit", "value", "window", "buffer", "client", "driver"]
REPEATS = ["", "}", "    return result", "end", "    pass", "# ----", "    }", "fi", "    break", ""]
DIRS = ["src", "lib/core", "docs", "conf", "web/static", "tools", "api/v2", "etc"]
EXTS = ["txt", "py", "md", "conf", "js", "ini", "sh", "c"]
NOEOL = "\\ No newline at end of file"


def fmt_range(start: int, length: int) -> str:
    beginning = start + 1
    if length == 1:
        return f"{beginning}"
    if not length:
        beginning -= 1
    return f"{beginning},{length}"


def elements(texts: list[str], final_nl: bool) -> list[tuple[str, bool]]:
    return [(t, final_nl or k < len(texts) - 1) for k, t in enumerate(texts)]


def render_hunks(a: list[tuple[str, bool]], b: list[tuple[str, bool]], ctx: int, body_end: str = "") -> tuple[list[str], list]:
    """Unified hunks between two element lists, and the opcode groups behind them."""
    out = []
    groups = list(SequenceMatcher(None, a, b, autojunk=False).get_grouped_opcodes(ctx))
    for group in groups:
        i1, i2, j1, j2 = group[0][1], group[-1][2], group[0][3], group[-1][4]
        out.append(f"@@ -{fmt_range(i1, i2 - i1)} +{fmt_range(j1, j2 - j1)} @@")
        for tag, a1, a2, b1, b2 in group:
            if tag == "equal":
                body = [(" ", e) for e in a[a1:a2]]
            else:
                body = [("-", e) for e in a[a1:a2]] + [("+", e) for e in b[b1:b2]]
            for kind, (text, nl) in body:
                out.append(kind + text + body_end)
                if not nl:
                    out.append(NOEOL)
    return out, groups


def content(texts: list[str], final_nl: bool, endings: list[str]) -> str:
    parts = []
    for k, t in enumerate(texts):
        last = k == len(texts) - 1
        parts.append(t + ("" if last and not final_nl else endings[k]))
    return "".join(parts)


class Gen:
    def __init__(self, seed: int, held_out: bool):
        self.r = random.Random(seed)
        self.held_out = held_out
        self.count = 0

    def fresh(self) -> str:
        r = self.r
        self.count += 1
        k = self.count
        w, v = r.choice(WORDS), r.choice(WORDS)
        forms = [f"{w}_{k} = {v}({r.randint(0, 99)})", f"    {w}.{v}_{k}()", f"# {w} {v} note {k}", f"set {w}{k} {v}",
                 f"    if {w}_{k} > {r.randint(1, 9)}: {v}()", f"{w}-{k}: {v}"]
        return r.choice(forms)

    def text_lines(self, count: int) -> list[str]:
        r = self.r
        out = []
        while len(out) < count:
            if self.held_out and r.random() < 0.3:
                out.append(r.choice(REPEATS))
            elif self.held_out and len(out) > 4 and r.random() < 0.06:
                start = r.randrange(len(out) - 3)
                out += out[start:start + r.randint(3, 8)]
            else:
                out.append(self.fresh())
        return out[:count]

    def edit(self, a: list[str]) -> list[str]:
        r = self.r
        b = list(a)
        spots = sorted(r.sample(range(len(a) + 1), min(len(a) + 1, r.randint(1, 4))), reverse=True)
        for s in spots:
            kind = r.choice(["replace", "replace", "insert", "delete"])
            if kind == "insert" or s >= len(b):
                b[s:s] = [self.fresh() for _ in range(r.randint(1, 3))]
            elif kind == "delete":
                del b[s:s + r.randint(1, 3)]
            else:
                b[s:s + r.randint(1, 3)] = [self.fresh() for _ in range(r.randint(1, 3))]
        return b

    def path(self, used: set) -> str:
        r = self.r
        while True:
            name = f"{r.choice(WORDS)}{r.randint(1, 99)}"
            if self.held_out and r.random() < 0.15:
                name = f"{r.choice(WORDS)} {name}"
            p = f"{r.choice(DIRS)}/{name}.{r.choice(EXTS)}"
            if p not in used:
                used.add(p)
                return p

    def endings(self, n: int, crlf: bool) -> list[str]:
        r = self.r
        if self.held_out and r.random() < 0.12:
            return [r.choice(["\n", "\r\n"]) for _ in range(n)]
        return ["\r\n" if crlf else "\n"] * n

    def stamp(self) -> str:
        r = self.r
        return f"2026-{r.randint(1, 12):02d}-{r.randint(1, 28):02d} {r.randint(0, 23):02d}:{r.randint(0, 59):02d}:{r.randint(0, 59):02d}.{r.randint(0, 999999999):09d} +0000"

    def header(self, style: str, path: str, action: str) -> list[str]:
        r = self.r
        prefix = {"git": ("a/", "b/"), "stamp": ("a/", "b/"), "plain": ("", ""), "deep": ("old/rel-1.4/", "new/rel-1.5/")}[style]
        old = "/dev/null" if action == "create" else prefix[0] + path
        new = "/dev/null" if action == "delete" else prefix[1] + path
        out = []
        if style == "git":
            out.append(f"diff --git a/{path} b/{path}")
            if action == "create":
                out.append("new file mode 100644")
            if action == "delete":
                out.append("deleted file mode 100644")
            out.append(f"index {r.randrange(16 ** 7):07x}..{r.randrange(16 ** 7):07x}" + (" 100644" if action == "modify" else ""))
            return out + [f"--- {old}", f"+++ {new}"]
        if style == "stamp":
            return out + [f"--- {old}\t{self.stamp()}", f"+++ {new}\t{self.stamp()}"]
        if r.random() < 0.3:
            out.append(f"Only in {r.choice(DIRS)}: {r.choice(WORDS)}.bak")
        return out + [f"--- {old}", f"+++ {new}"]

    def perturb(self, base: list[str], groups: list, side: int, allow_decoy: bool) -> list[str]:
        """The target lines: base with lines moved, edge context changed, a hunk line changed, or decoys added."""
        r = self.r
        t = list(base)
        lo_i, hi_i = (1, 2) if side == 0 else (3, 4)
        ranges = [(g[0][lo_i], g[-1][hi_i]) for g in groups]
        if r.random() < 0.3:
            g = r.choice(groups)
            ends = []
            if g[0][0] == "equal":
                run = g[0][hi_i] - g[0][lo_i]
                ends.append(g[0][lo_i] + (1 if run > 1 and r.random() < 0.3 else 0))
            if g[-1][0] == "equal":
                run = g[-1][hi_i] - g[-1][lo_i]
                ends.append(g[-1][hi_i] - 1 - (1 if run > 1 and r.random() < 0.3 else 0))
            if ends:
                t[r.choice(ends)] = self.fresh()
        if r.random() < (0.15 if self.held_out else 0.1):
            changed = [k for g in groups for op in g if op[0] != "equal" for k in range(op[lo_i], op[hi_i])]
            if changed:
                t[r.choice(changed)] = self.fresh()
        gaps = [0, len(base)] + [hi for _, hi in ranges] + [lo for lo, _ in ranges]
        gaps += [k for k in range(len(base)) if all(not (lo < k < hi) for lo, hi in ranges)]
        moves = []
        if r.random() < 0.55:
            moves.append(("insert", r.choice(gaps), [self.fresh() for _ in range(r.randint(1, 9))]))
        if r.random() < 0.25:
            free = [k for k in range(len(base)) if all(not (lo <= k < hi) for lo, hi in ranges)]
            if free:
                k = r.choice(free)
                m = 1
                while m < 6 and k + m in free:
                    m += 1
                moves.append(("delete", k, m))
        if allow_decoy and r.random() < 0.3:
            lo, hi = r.choice(ranges)
            if hi > lo:
                moves.append(("insert", r.choice(gaps), base[lo:hi]))
        for kind, k, arg in sorted(moves, key=lambda m: -m[1]):
            if kind == "insert":
                t[k:k] = arg
            else:
                del t[k:k + arg]
        return t

    def section(self, style: str, path: str, action: str, reverse: bool, files: dict, out: list) -> None:
        r = self.r
        held = self.held_out
        n = r.randint(3, 110) if held else r.randint(6, 60)
        if action == "create":
            a, b = [], self.text_lines(n)
        elif action == "delete":
            a, b = self.text_lines(n), []
        else:
            a = self.text_lines(n)
            b = self.edit(a)
        a_nl = b_nl = True
        if held:
            a_nl, b_nl = r.random() > 0.2, r.random() > 0.2
        elif action == "modify" and not reverse and r.random() < 0.15:
            a_nl = b_nl = False
            b[-1] = self.fresh()
            if r.random() < 0.3:
                b_nl = True
        ea, eb = elements(a, a_nl), elements(b, b_nl)
        ctx = r.choice([3, 3, 3, 3, 2, 1, 0] if held else [3, 3, 3, 3, 2, 1, 0])
        if action != "modify":
            ctx = 3
        crlf = r.random() < 0.2
        crlf_patch = held and crlf and r.random() < 0.5
        lines, groups = render_hunks(ea, eb, ctx, "\r" if crlf_patch else "")
        out += self.header(style, path, action) + lines
        side = 1 if reverse else 0
        base, base_nl = (b, b_nl) if reverse else (a, a_nl)
        if (action, reverse) in (("create", False), ("delete", True)):
            return
        if action == "modify" or (held and r.random() < 0.3):
            base = self.perturb(base, groups, side, held)
        files[path] = content(base, base_nl, self.endings(len(base), crlf))

    def options(self, strip: int, reverse: bool) -> dict:
        r = self.r
        opts = {}
        if strip != 1 or r.random() < 0.2:
            opts["strip"] = strip
        if r.random() < 0.3:
            opts["fuzz"] = r.choice([0, 1, 2, 3])
        if reverse or r.random() < 0.1:
            opts["reverse"] = reverse
        return opts

    def random_case(self) -> dict:
        r = self.r
        style = r.choice(["git", "git", "stamp", "plain", "deep"])
        strip = {"git": 1, "stamp": 1, "plain": 0, "deep": 2}[style]
        reverse = r.random() < 0.25
        used: set = set()
        files: dict = {}
        out: list = []
        if r.random() < 0.3:
            out += [f"From {r.randrange(16 ** 12):012x} Mon Sep 17 00:00:00 2001", f"Subject: [PATCH] update {r.choice(WORDS)}", ""]
        for _ in range(r.choice([1, 1, 1, 2, 2, 3])):
            action = r.choices(["modify", "create", "delete"], [0.84, 0.09, 0.07])[0]
            sec_style = r.choice(["git", "stamp"]) if strip == 1 else style
            self.section(sec_style, self.path(used), action, reverse, files, out)
        for _ in range(r.choice([0, 0, 1, 2])):
            p = self.path(used)
            files[p] = content(self.text_lines(r.randint(2, 12)), True, ["\n"] * 12)
        doc = {"patch": "\n".join(out) + "\n", "files": dict(sorted(files.items()))}
        opts = self.options(strip, reverse)
        if opts:
            doc["options"] = opts
        return doc

    def broken_case(self, i: int) -> dict:
        r = self.r
        doc = self.random_case()
        lines = doc["patch"].split("\n")
        kind = i % 8
        if kind == 0:
            k = max(j for j, line in enumerate(lines) if line.startswith("@@"))
            del lines[k + 1:]
            lines.append(" " + self.fresh() if r.random() < 0.5 else "*" + self.fresh())
        elif kind == 1:
            k = next(j for j, line in enumerate(lines) if line.startswith("--- "))
            lines[k] = "--- a/../" + r.choice(["etc/passwd", "outside.txt"])
        elif kind == 2:
            doc["files"] = {}
        elif kind == 3:
            doc["options"] = r.choice([{"fuzz": 7}, {"strip": "1"}, {"reverse": "yes"}, {"dry_run": True}, {"fuzz": True}])
        elif kind == 4:
            k = next(j for j, line in enumerate(lines) if line.startswith("+++ "))
            lines[k] = lines[k].replace(".", "-renamed.", 1) if "/dev/null" not in lines[k] else lines[k]
            if "/dev/null" in lines[k]:
                lines.insert(0, "@@ -1 +1 @@")
        elif kind == 5:
            k = next(j for j, line in enumerate(lines) if line.startswith("--- "))
            end = next((j for j in range(k + 2, len(lines)) if lines[j].startswith("--- ")), len(lines))
            lines = lines[:end] + lines[k:end] + lines[end:]
        elif kind == 6:
            k = next(j for j, line in enumerate(lines) if line.startswith("@@"))
            lines.insert(k + 1, NOEOL)
            if lines[k + 2].startswith(("-", "+", " ")):
                lines[k + 1], lines[k + 2] = lines[k + 2], NOEOL
        else:
            k = next(j for j, line in enumerate(lines) if line.startswith("@@"))
            lines[k] = lines[k].replace(" @@", ",x @@", 1)
        doc["patch"] = "\n".join(lines)
        return doc


def crafted() -> list[dict]:
    """Visible cases that each exercise one rule the random visible cases keep away from."""
    g = Gen(9917, False)
    out = []

    # Fuzz levels before positions (apply.md 3.4): a fuzz 1 match where the hunk is stated, an exact copy ten lines down.
    a = [g.fresh() for _ in range(40)]
    b = list(a)
    b[14] = g.fresh()
    lines, groups = render_hunks(elements(a, True), elements(b, True), 3)
    t = list(a)
    region = a[11:18]
    t[11] = g.fresh()
    t[28:28] = region
    out.append({"patch": "\n".join(["--- a/src/order.py", "+++ b/src/order.py"] + lines) + "\n",
                "files": {"src/order.py": content(t, True, ["\n"] * len(t))}})

    # A reverse patch swaps the sides of the end-of-file markers (patch.md 7).
    a = [g.fresh() for _ in range(12)]
    b = a[:-1] + [g.fresh()]
    lines, _ = render_hunks(elements(a, False), elements(b, True), 3)
    out.append({"patch": "\n".join(["diff --git a/conf/limits.ini b/conf/limits.ini", "index 3f2a1c0..9be4d17 100644", "--- a/conf/limits.ini", "+++ b/conf/limits.ini"] + lines) + "\n",
                "files": {"conf/limits.ini": content(b, True, ["\n"] * len(b))}, "options": {"reverse": True}})

    # A hunk never applies before the end of the hunk before it (apply.md 3.3).
    a = [g.fresh() for _ in range(70)]
    b = list(a)
    b[23] = g.fresh()
    b[37] = g.fresh()
    lines, groups = render_hunks(elements(a, True), elements(b, True), 3)
    h2 = a[34:41]
    t = h2 + a[10:30] + [g.fresh() for _ in range(40)] + a[30:]
    out.append({"patch": "\n".join(["--- a/lib/core/queue.c", "+++ b/lib/core/queue.c"] + lines) + "\n",
                "files": {"lib/core/queue.c": content(t, True, ["\n"] * len(t))}})

    # A patch made from a file with CRLF endings carries them on its hunk lines (patch.md 1.2).
    a = [g.fresh() for _ in range(25)]
    b = g.edit(a)
    lines, _ = render_hunks(elements(a, True), elements(b, True), 3, "\r")
    out.append({"patch": "\n".join(["--- a/web/static/site.js", "+++ b/web/static/site.js"] + lines) + "\n",
                "files": {"web/static/site.js": content(a, True, ["\r\n"] * len(a))}})

    # A path ends at the first tab; spaces belong to it (patch.md 2.2).
    a = [g.fresh() for _ in range(18)]
    b = g.edit(a)
    lines, _ = render_hunks(elements(a, True), elements(b, True), 3)
    out.append({"patch": "\n".join(["--- docs/release notes.md\t2026-05-02 09:14:00.000000000 +0000", "+++ docs/release notes.md\t2026-05-03 11:02:41.000000000 +0000"] + lines) + "\n",
                "files": {"docs/release notes.md": content(a, True, ["\n"] * len(a))}, "options": {"strip": 0}})
    return out


def generate(root: Path, seed: int, cases: int = 150, held_out: bool = False) -> None:
    root = Path(root)
    g = Gen(seed, held_out)
    (root / "cases").mkdir(parents=True, exist_ok=True)
    docs = [g.random_case() for _ in range(cases)]
    extra = [g.broken_case(i) for i in range(max(8, cases // 16))]
    if not held_out:
        extra += crafted()
    for pos, doc in zip(g.r.sample(range(cases), len(extra)), extra):
        docs[pos] = doc
    for i, doc in enumerate(docs):
        (root / "cases" / f"case-{i + 1:03d}.json").write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
