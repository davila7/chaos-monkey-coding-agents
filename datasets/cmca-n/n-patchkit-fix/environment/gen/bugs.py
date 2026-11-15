"""Edits that turn the package sources under src/ into the tree shipped in /app.

Each entry is (id, file under patchkit/, text in src, text shipped). An id may
have several entries. The ids group them: V entries fail the shipped unit
tests, R entries pass them and show in tools/check.py, X entries pass both and
the visible data exercises each on exactly one case (build.py checks it);
held-out data exercises them often.
"""

from pathlib import Path

BUGS = [
    # A range without a count is read as empty.
    ("V1", "parse.py",
     "    a, b = int(m[1]), int(m[2]) if m[2] is not None else 1\n    c, d = int(m[3]), int(m[4]) if m[4] is not None else 1\n",
     "    a, b = int(m[1]), int(m[2]) if m[2] is not None else 0\n    c, d = int(m[3]), int(m[4]) if m[4] is not None else 0\n"),
    # A hunk with no old lines is placed one line early.
    ("V2", "apply.py",
     "    return h.old_start - 1 if h.old_len else h.old_start\n",
     "    return h.old_start - 1\n"),
    # Added lines always end with LF.
    ("V3", "apply.py",
     '            out.append((hl.text, ending if hl.new_eol else ""))\n',
     '            out.append((hl.text, "\\n" if hl.new_eol else ""))\n'),
    # Of two positions at the same distance, the later one is tried first.
    ("V4", "search.py",
     "    return sorted(range(lo, hi + 1), key=lambda p: (abs(p - expected), p))\n",
     "    return sorted(range(lo, hi + 1), key=lambda p: (abs(p - expected), -p))\n"),
    # 'moved' also counts hunks that only needed fuzz.
    ("R1", "report.py",
     '            "moved": sum(h["offset"] != 0 for h in applied),\n',
     '            "moved": sum(h["offset"] != 0 or h["fuzz"] > 0 for h in applied),\n'),
    # The offset is reported from the expected position, not from the stated line.
    ("R2", "apply.py",
     '"offset": line - stated, "fuzz": m.fuzz})\n',
     '"offset": line - stated - carry, "fuzz": m.fuzz})\n'),
    # Files are listed in path order instead of patch order.
    ("R3", "report.py",
     "    named = {path for _, _, path in sections}\n",
     '    entries.sort(key=lambda e: e["path"])\n    named = {path for _, _, path in sections}\n'),
    # Every position is tried at every fuzz level before the next position.
    ("X1", "search.py",
     "    tries.sort(key=lambda t: (t[0], t[1]))\n",
     "    tries.sort(key=lambda t: (t[1], t[0]))\n"),
    # A reverse patch keeps the end-of-file markers on their sides.
    ("X2", "parse.py",
     "        body = [HunkLine(flip[hl.kind], hl.text, hl.new_eol, hl.old_eol) for hl in h.lines]\n",
     "        body = [HunkLine(flip[hl.kind], hl.text, hl.old_eol, hl.new_eol) for hl in h.lines]\n"),
    # A hunk may match before the end of the hunk before it.
    ("X3", "search.py",
     "def locate(h: Hunk, lines: list[Line], start: int, floor: int, fuzz: int) -> Match | None:\n"
     '    """start: the expected index of the first old line; floor: the first index the hunk may use."""\n',
     "def locate(h: Hunk, lines: list[Line], start: int, fuzz: int) -> Match | None:\n"
     '    """start: the expected index of the first old line."""\n'),
    ("X3", "search.py",
     "        for rank, p in enumerate(candidates(start + top, floor, len(lines) - n)):\n",
     "        for rank, p in enumerate(candidates(start + top, 0, len(lines) - n)):\n"),
    ("X3", "apply.py",
     "    carry, floor = 0, 0\n",
     "    carry = 0\n"),
    ("X3", "apply.py",
     "        m = locate(h, lines, expected_start(h) + carry, floor, fuzz)\n",
     "        m = locate(h, lines, expected_start(h) + carry, fuzz)\n"),
    ("X3", "apply.py",
     "        floor = m.pos + n\n",
     ""),
    # A carriage return before the newline stays in the hunk line.
    ("X4", "parse.py",
     '    return [line[:-1] if line.endswith("\\r") else line for line in lines]\n',
     "    return lines\n"),
    # A path ends at the first space or tab.
    ("X5", "parse.py",
     '    path = rest.split("\\t", 1)[0]\n',
     '    path = re.split(r"\\s", rest, maxsplit=1)[0]\n'),
]


def apply(package_dir: Path, ids) -> None:
    """Applies the named bugs to a copy of the patchkit package in place."""
    for bug_id, rel, good, bad in BUGS:
        if bug_id not in ids:
            continue
        p = Path(package_dir) / rel
        text = p.read_text(encoding="utf-8")
        if text.count(good) != 1:
            raise SystemExit(f"{bug_id} {rel}: expected one match")
        p.write_text(text.replace(good, bad, 1), encoding="utf-8")


ALL = sorted({b[0] for b in BUGS})
