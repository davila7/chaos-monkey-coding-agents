"""Edits that turn the package sources under src/ into the tree shipped in /app.

Each entry is (id, cause class, file under stockroom/, text in src, text
shipped). The B entries are shipped. D1 is the defect of release 2.6.0, fixed
in 2.6.1: build.py applies it only to the runs the logs date before 2.6.1.

ACCEPT lists, per shipped bug, text that marks each line a report may name
for that cause: the defective lines and the line that brings the defect in.
"""

from pathlib import Path

BUGS = [
    ("B1", "shared-state", "settings.py",
     "    out = {key: dict(value) if isinstance(value, dict) else value for key, value in DEFAULTS.items()}\n",
     "    out = dict(DEFAULTS)\n"),
    ("B2", "cache-key", "rates.py",
     '    try:\n        key = json.dumps(spec, sort_keys=True, separators=(",", ":"))\n    except (TypeError, ValueError):\n        raise RateError("a rate table must be plain JSON") from None\n',
     '    try:\n        key = (spec["carrier"], spec["service"], spec["effective"])\n    except (KeyError, TypeError):\n        raise RateError("a rate table needs carrier, service and effective") from None\n'),
    ("B2", "cache-key", "rates.py",
     "import json\nimport math\n",
     "import math\n"),
    ("B3", "hash-order", "bins.py",
     "    return min(candidates, key=lambda code: (distance(origin, code), code))\n",
     "    return min(candidates, key=lambda code: distance(origin, code))\n"),
    ("B4", "clock", "reorder.py",
     "    return date(y, m, min(day, calendar.monthrange(y, m)[1]))\n",
     "    return date(y, m, day)\n"),
    ("B4", "clock", "reorder.py",
     "import calendar\nimport math\n",
     "import math\n"),
    ("B5", "timezone", "clock.py",
     "    return now().date()\n",
     "    return date.fromtimestamp(now().timestamp())\n"),
    ("B6", "temp-file", "export.py",
     '        fd, name = tempfile.mkstemp(prefix=f".{self.target.name}.", suffix=".part", dir=self.target.parent)\n        self._spool = Path(name)\n        self._fh = os.fdopen(fd, "w", encoding="utf-8", newline="")\n',
     '        spool = Path(tempfile.gettempdir()) / "stockroom-spool"\n        spool.mkdir(exist_ok=True)\n        self._spool = spool / f"{self.target.name}.part"\n        self._fh = open(self._spool, "a", encoding="utf-8", newline="")\n'),
    ("B6", "temp-file", "export.py",
     "        if exc_type is None:\n            os.replace(self._spool, self.target)\n        else:\n            self._spool.unlink(missing_ok=True)\n",
     "        if exc_type is None:\n            os.replace(self._spool, self.target)\n"),
    ("D1", "", "units.py",
     "    grams = Decimal(str(value)) * _factor(GRAMS, from_unit)\n",
     "    grams = Decimal(str(value)).quantize(_quantum(places), rounding=ROUND_HALF_EVEN) * _factor(GRAMS, from_unit)\n"),
]

ACCEPT = {
    "B1": ["out = dict(DEFAULTS)", "out[key].update(value)"],
    "B2": ['key = (spec["carrier"], spec["service"], spec["effective"])'],
    "B3": ["candidates = {b.code for b in pool", "return min(candidates, key=lambda code: distance(origin, code))"],
    "B4": ["return date(y, m, day)"],
    "B5": ["return date.fromtimestamp(now().timestamp())"],
    "B6": ['spool = Path(tempfile.gettempdir()) / "stockroom-spool"', 'self._spool = spool / f"{self.target.name}.part"',
           'self._fh = open(self._spool, "a"', "if exc_type is None:", "os.replace(self._spool, self.target)"],
}

SHIPPED = sorted({b[0] for b in BUGS if b[0].startswith("B")})
CLASSES = {b[0]: b[1] for b in BUGS if b[1]}
FILES = {b[0]: f"stockroom/{b[2]}" for b in BUGS}


def apply(package_dir: Path, ids) -> None:
    """Applies the named edits to a copy of the stockroom package in place."""
    for bug_id, _, rel, good, bad in BUGS:
        if bug_id not in ids:
            continue
        p = Path(package_dir) / rel
        text = p.read_text(encoding="utf-8")
        if text.count(good) != 1:
            raise SystemExit(f"{bug_id} {rel}: expected one match")
        p.write_text(text.replace(good, bad, 1), encoding="utf-8")


def lines(package_dir: Path, bug_id: str) -> list[int]:
    """Line numbers, in the shipped package, of the lines a report may name for bug_id."""
    out = []
    for marker in ACCEPT[bug_id]:
        text = (Path(package_dir) / FILES[bug_id][len("stockroom/"):]).read_text(encoding="utf-8").splitlines()
        hits = [i + 1 for i, l in enumerate(text) if marker in l]
        if len(hits) != 1:
            raise SystemExit(f"{bug_id}: {marker!r} marks {len(hits)} lines")
        out += hits
    return sorted(out)
