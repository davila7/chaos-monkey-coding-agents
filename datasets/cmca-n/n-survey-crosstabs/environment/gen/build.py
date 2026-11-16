"""Builds the /app tree: docs, tools, unit tests, the survey under data/ and the
approved table digests the check tool reads.

Usage: python3 build.py OUT_DIR

The output depends only on SEED and the files next to this script.
"""

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "src" / "tests"))

import datagen  # noqa: E402
from test_tables import first_difference  # noqa: E402

SEED = 4417
COUNTS = ("rows", "duplicates", "short_partials", "speeders", "complete", "partial")


def copy_tree(src: Path, dst: Path) -> None:
    for p in sorted(src.rglob("*")):
        if "__pycache__" in p.parts:
            continue
        rel = p.relative_to(src)
        if p.is_dir():
            (dst / rel).mkdir(parents=True, exist_ok=True)
        else:
            (dst / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, dst / rel)


def reference(data: Path, out: Path) -> dict:
    subprocess.run([sys.executable, "-B", str(HERE / "tabref.py"), str(data), str(out)], check=True,
                   capture_output=True)
    return json.loads(out.read_text(encoding="utf-8"))


def text(v, count=False):
    if v is None:
        return "null"
    return str(v) if count else f"{v + 0.0:.2f}"


def build(out: Path) -> None:
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"{out} is not empty")
    out.mkdir(parents=True, exist_ok=True)
    copy_tree(HERE / "src", out)
    datagen.generate(out / "data", SEED)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        for case in sorted(p.name for p in (out / "tests" / "fixtures").iterdir()):
            got = reference(out / "tests" / "fixtures" / case / "input", td / f"{case}.json")
            want = json.loads((out / "tests" / "fixtures" / case / "expected.json").read_text(encoding="utf-8"))
            if first_difference(got, want) is not None:
                raise SystemExit(f"fixture {case}: the reviewed tables differ from the reference")
        ref = reference(out / "data", td / "tables.json")
    salt = hashlib.sha256(f"tables|{SEED}".encode()).hexdigest()[:16]
    entries = {}

    def put(key, value, count=False):
        entries[key] = hashlib.sha256(f"{salt}|{key}|{text(value, count)}".encode()).hexdigest()[:24]

    s = ref["summary"]
    for v in s["versions"]:
        for k in COUNTS:
            put(f"summary {v['version']} {k}", v[k], True)
    put("summary respondents", s["respondents"], True)
    for k in ("effective_n", "weight_min", "weight_max"):
        put(f"summary {k}", s[k])
    tables = []
    for t in ref["tables"]:
        rows = list(t["columns"][0]["values"])
        for c in t["columns"]:
            put(f"{t['table']} {c['column']} base", c["base"], True)
            put(f"{t['table']} {c['column']} weighted_base", c["weighted_base"])
            for r in rows:
                put(f"{t['table']} {c['column']} {r}", c["values"][r])
        tables.append({"table": t["table"], "columns": [c["column"] for c in t["columns"]], "rows": rows,
                       "size": len(t["columns"]) * (2 + len(rows))})
    approved = {"salt": salt, "versions": [v["version"] for v in s["versions"]], "tables": tables,
                "entries": entries}
    (out / "tools" / "approved-tables.json").write_text(json.dumps(approved, indent=0) + "\n", encoding="utf-8")
    (out / "bin").mkdir(exist_ok=True)
    (out / "out").mkdir(exist_ok=True)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    build(Path(sys.argv[1]))
