"""Edits that turn the package sources under src/ into the tree shipped in /app.

Each entry is (id, file under layercfg/, text in src, text shipped). The ids
group them: V entries fail the shipped unit tests, R entries pass them and
show in tools/check.py, X entries pass both and the visible data exercises
each on exactly one config (build.py checks it); held-out data exercises them
often.
"""

from pathlib import Path

BUGS = [
    # The separator is the first ':' when the line has one, else the first '='.
    ("V1", "lexer.py",
     '    found = [p for p in (s.find("="), s.find(":")) if p >= 0]\n    return min(found) if found else -1\n',
     '    if ":" in s:\n        return s.find(":")\n    return s.find("=")\n'),
    # '\$' gives a '$' that interpolation still reads as the start of a reference.
    ("V2", "values.py",
     "# '\\$' becomes '$$', which interpolation writes as one '$' (interp.md 2.2).\nESCAPES = {\"\\\\\": \"\\\\\", '\"': '\"', \"n\": \"\\n\", \"t\": \"\\t\", \"$\": \"$$\"}\n",
     "ESCAPES = {\"\\\\\": \"\\\\\", '\"': '\"', \"n\": \"\\n\", \"t\": \"\\t\", \"$\": \"$\"}\n"),
    # Every '#' of an unquoted value starts a comment.
    ("V3", "values.py",
     '    """Removes an inline comment: a \'#\' right after a space or tab, and everything after it."""\n    for i, c in enumerate(raw):\n        if c == "#" and i > 0 and raw[i - 1] in " \\t":\n',
     '    """Removes an inline comment and everything after it."""\n    for i, c in enumerate(raw):\n        if c == "#":\n'),
    # 'ms' is read as 'm' followed by a stray 's'.
    ("V4", "convert.py",
     'DURATION_PART = re.compile(r"([0-9]+)(ms|d|h|m|s)")\n',
     'DURATION_PART = re.compile(r"([0-9]+)(d|h|m|s|ms)")\n'),
    ("R1", "report.py",
     "    for section in sorted(s for s in store if written(s)):\n",
     "    for section in sorted(store):\n"),
    ("R2", "convert.py",
     "    return [item for item in items if item]\n",
     "    return items if text else []\n"),
    ("R3", "loader.py",
     "        if name not in self.includes:\n            self.includes.append(name)\n",
     "        self.includes.append(name)\n"),
    # KB, MB, GB and TB are read as powers of 1024.
    ("X1", "convert.py",
     'SIZE_UNITS = {"B": 1, "KB": 1000, "MB": 1000 ** 2, "GB": 1000 ** 3, "TB": 1000 ** 4,\n',
     'SIZE_UNITS = {"B": 1, "KB": 1024, "MB": 1024 ** 2, "GB": 1024 ** 3, "TB": 1024 ** 4,\n'),
    # A reference is resolved when its line is applied, against what has been read so far.
    ("X2", "interp.py",
     "    for a in assignments:\n        store.setdefault(a.section, {})[a.key] = a\n",
     "    for a in assignments:\n        if a.interp:\n            a = Assignment(a.section, a.key, Resolver(store).expand(a.section, a.text, (), a.where), False, a.where)\n        store.setdefault(a.section, {})[a.key] = a\n"),
    # The section of a reference ends at its first dot.
    ("X3", "interp.py",
     '            target, key = name.rsplit(".", 1)\n',
     '            target, key = name.split(".", 1)\n'),
    # After an include, the including file goes on in the section the shared file ended in.
    ("X4", "loader.py",
     "                self._include(line.name, where)\n",
     "                section = self._include(line.name, where)\n"),
]


def apply(package_dir: Path, ids) -> None:
    """Applies the named bugs to a copy of the layercfg package in place."""
    for bug_id, rel, good, bad in BUGS:
        if bug_id not in ids:
            continue
        p = Path(package_dir) / rel
        text = p.read_text(encoding="utf-8")
        if text.count(good) != 1:
            raise SystemExit(f"{bug_id} {rel}: expected one match")
        p.write_text(text.replace(good, bad, 1), encoding="utf-8")


ALL = sorted({b[0] for b in BUGS})
