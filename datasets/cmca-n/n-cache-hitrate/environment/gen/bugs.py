"""Edits that turn the package sources under src/ into the tree shipped in /app.

Each entry is (id, cause class, file under shelfmark/, text in src, text
shipped). The B entries are shipped in 2.4.0. D1 is the defect of release
2.3.1 that 2.4.0 fixed: build.py applies it, without the B entries, to the
requests served before the 2.4.0 deploy.

ACCEPT gives, per shipped defect, the file and the markers of the lines a
report may name.
"""

from pathlib import Path

BUGS = [
    ("B1", "key-vary", "locale.py",
     "            if primary(low) == primary(rng):\n                return loc\n",
     "            if primary(low) == primary(rng):\n                return rng\n"),
    ("B2", "key-params", "keys.py",
     '        if name in cfg.ignore_params or name.startswith("utm_"):\n',
     "        if name in cfg.ignore_params:\n"),
    ("B3", "ttl", "config.py",
     "        return value * 1000\n",
     "        return int(value)\n"),
    ("B4", "invalidation", "cache.py",
     '        prefix = f"{route}|{ident}|"\n',
     '        prefix = f"{route}|{ident}"\n'),
    ("D1", "key-normalize", "keys.py",
     '        if name == "q":\n            value = normalize_q(value)\n',
     ""),
]

SHIPPED = ("B1", "B2", "B3", "B4")
OLD = ("D1",)

ACCEPT = {
    "B1": ("locale.py", ["return rng"]),
    "B2": ("keys.py", ["if name in cfg.ignore_params:"]),
    "B3": ("config.py", ["return int(value)"]),
    "B4": ("cache.py", ['prefix = f"{route}|{ident}"']),
}


def apply(pkg: Path, ids) -> None:
    for bug_id, _, rel, old, new in BUGS:
        if bug_id not in ids:
            continue
        p = pkg / rel
        text = p.read_text(encoding="utf-8")
        if text.count(old) != 1:
            raise SystemExit(f"{bug_id}: {rel}: expected one match of {old!r}")
        p.write_text(text.replace(old, new, 1), encoding="utf-8")


def accepted_lines(pkg: Path, bug_id: str) -> list[int]:
    rel, markers = ACCEPT[bug_id]
    lines = (pkg / rel).read_text(encoding="utf-8").splitlines()
    hits = [i + 1 for i, line in enumerate(lines) if any(m in line for m in markers)]
    if len(hits) != len(markers):
        raise SystemExit(f"{bug_id}: markers match lines {hits}")
    return hits
