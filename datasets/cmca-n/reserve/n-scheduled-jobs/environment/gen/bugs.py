"""Edits that turn the package sources under src/ into the tree shipped in /app.

Each entry is (id, cause class, file under spokehouse/, text in src, text
shipped). The B entries are shipped. D1 is the defect of release 4.1.2, fixed
in 4.2.0: build.py applies it, on top of the B entries, to the runs before the
4.2.0 deploy.

ACCEPT gives, per shipped defect, the first and the last marker of the lines
a report may name: the defective lines, or for B4 the whole save path that
lacks the check.
"""

from pathlib import Path

BUGS = [
    ("B1", "retention", "jobs/compact.py",
     "    cutoff = now - timedelta(days=settings.RETENTION_DAYS)\n",
     "    cutoff = now - timedelta(hours=settings.RETENTION_DAYS)\n"),
    ("B2", "time-compare", "jobs/holds.py",
     '        if parse_ts(hold["until"]) <= now:\n',
     '        if hold["until"] <= fmt_ts(now):\n'),
    ("B2", "time-compare", "jobs/holds.py",
     "from ..timeutil import parse_ts\n",
     "from ..timeutil import fmt_ts, parse_ts\n"),
    ("B3", "rounding", "fares.py",
     "    return -(-seconds // 60)\n",
     "    return seconds // 60\n"),
    ("B4", "lost-update", "store.py",
     '    current = load(path)["meta"]["rev"]\n    if current != state["meta"]["rev"]:\n        raise StaleState(f"{path} is at rev {current}, the state was loaded at rev {state[\'meta\'][\'rev\']}")\n    out = data(state)\n    out["meta"] = {"rev": current + 1,',
     '    out = data(state)\n    out["meta"] = {"rev": state["meta"]["rev"] + 1,'),
    ("D1", "capacity", "jobs/holds.py",
     '            del out["holds"][hold_id]\n            dock = out["docks"][hold["dock"]]\n            dock["bikes"] = min(dock["capacity"], dock["bikes"] + 1)\n',
     '            del out["holds"][hold_id]\n'),
]

SHIPPED = ("B1", "B2", "B3", "B4")

ACCEPT = {
    "B1": ("jobs/compact.py", ["cutoff = now - timedelta(hours="], None),
    "B2": ("jobs/holds.py", ['if hold["until"] <= fmt_ts(now):'], None),
    "B3": ("fares.py", ["return seconds // 60"], None),
    "B4": ("store.py", ["def save(path, state: dict"], "os.replace(tmp, path)"),
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
    rel, markers, last = ACCEPT[bug_id]
    lines = (pkg / rel).read_text(encoding="utf-8").splitlines()
    hits = [i + 1 for i, line in enumerate(lines) if any(m in line for m in markers)]
    if len(hits) != 1:
        raise SystemExit(f"{bug_id}: markers match lines {hits}")
    if last is None:
        return hits
    end = [i + 1 for i, line in enumerate(lines) if last in line]
    if len(end) != 1 or end[0] < hits[0]:
        raise SystemExit(f"{bug_id}: end marker matches lines {end}")
    return list(range(hits[0], end[0] + 1))
