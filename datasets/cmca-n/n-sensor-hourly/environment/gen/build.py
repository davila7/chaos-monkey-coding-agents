"""Builds the /app tree: docs, tools, unit tests, the dumps under data/ and the
approved hourly digests the check tool reads.

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

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import datagen  # noqa: E402

SEED = 5521
QUANTITIES = ("temp", "rh", "pres", "wspd", "wdir", "rain")


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
    subprocess.run([sys.executable, "-B", str(HERE / "hourlyref.py"), str(data), str(out)], check=True,
                   capture_output=True)
    return json.loads(out.read_text(encoding="utf-8"))


def close(a, b, q):
    if a is None or b is None:
        return a is b
    d = abs(a - b)
    if q == "wdir":
        d = min(d, 360 - d)
    return d <= 0.011


def same(got, want) -> bool:
    if [(s["station"], s["interval_s"], [h["hour"] for h in s["hours"]]) for s in got["stations"]] != \
            [(s["station"], s["interval_s"], [h["hour"] for h in s["hours"]]) for s in want["stations"]]:
        return False
    for gs, ws in zip(got["stations"], want["stations"]):
        for gh, wh in zip(gs["hours"], ws["hours"]):
            for q in QUANTITIES:
                if gh[q]["n"] != wh[q]["n"] or not close(gh[q]["value"], wh[q]["value"], q):
                    return False
    return True


def value_text(v):
    return "null" if v is None else f"{v:.2f}"


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
            if not same(got, want):
                raise SystemExit(f"fixture {case}: the reviewed hourly file differs from the reference")
        ref = reference(out / "data", td / "hourly.json")
    salt = hashlib.sha256(f"hourly|{SEED}".encode()).hexdigest()[:16]
    approved = {"salt": salt, "stations": [], "values": {}}
    for s in ref["stations"]:
        approved["stations"].append({"station": s["station"], "interval_s": s["interval_s"],
                                     "hours": [h["hour"] for h in s["hours"]]})
        for h in s["hours"]:
            for q in QUANTITIES:
                key = f"{s['station']} {h['hour']} {q}"
                text = f"{salt}|{key}|{h[q]['n']}|{value_text(h[q]['value'])}"
                approved["values"][key] = hashlib.sha256(text.encode()).hexdigest()[:24]
    (out / "tools" / "approved-hourly.json").write_text(json.dumps(approved, indent=0) + "\n", encoding="utf-8")
    (out / "bin").mkdir(exist_ok=True)
    (out / "out").mkdir(exist_ok=True)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    build(Path(sys.argv[1]))
