"""Builds the /app tree: the patchkit package, docs, tools, tests and the data directory.

Usage: python3 build.py OUT_DIR

The output depends only on SEED and the files next to this script.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bugs  # noqa: E402
import datagen  # noqa: E402

SEED = 4127
# Reviewed results are kept only where the package with the visible-test fixes
# alone already agrees with the rules.
REVIEW_BUGS = [b for b in bugs.ALL if not b.startswith("V")]


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


def run_package(package: Path, data: Path, out: Path) -> dict[str, str]:
    """Result text per case id, or the error class for a refused case."""
    subprocess.run([sys.executable, "-B", "-m", "patchkit", "run", "--data", str(data), "--out", str(out)], cwd=package.parent, check=True, capture_output=True)
    got = {p.stem: p.read_text(encoding="utf-8") for p in sorted((out / "results").glob("*.json"))}
    for e in json.loads((out / "errors.json").read_text(encoding="utf-8")):
        got[e["case"]] = "error " + e["error"].split(":", 1)[0]
    return got


def build(out: Path) -> None:
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"{out} is not empty")
    out.mkdir(parents=True, exist_ok=True)
    copy_tree(HERE / "src", out)
    datagen.generate(out / "data", SEED)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        copy_tree(HERE / "src" / "patchkit", td / "ref" / "patchkit")
        copy_tree(HERE / "src" / "patchkit", td / "part" / "patchkit")
        bugs.apply(td / "part" / "patchkit", REVIEW_BUGS)
        ref = run_package(td / "ref" / "patchkit", out / "data", td / "ref-out")
        part = run_package(td / "part" / "patchkit", out / "data", td / "part-out")
        # Each X entry must show on exactly one case of the visible data;
        # held-out data carries the rest.
        for bug_id in [b for b in bugs.ALL if b.startswith("X")]:
            copy_tree(HERE / "src" / "patchkit", td / bug_id / "patchkit")
            bugs.apply(td / bug_id / "patchkit", [bug_id])
            got = run_package(td / bug_id / "patchkit", out / "data", td / f"{bug_id}-out")
            hit = sorted(cid for cid in set(ref) | set(got) if ref.get(cid) != got.get(cid))
            if len(hit) != 1:
                raise SystemExit(f"{bug_id} shows on {len(hit)} visible cases, expected 1: {hit[:5]}")
    for cid, text in sorted(ref.items()):
        if not text.startswith("error ") and part.get(cid) == text:
            dst = out / "tests" / "expected" / "results" / f"{cid}.json"
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(text, encoding="utf-8")
    bugs.apply(out / "patchkit", bugs.ALL)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    build(Path(sys.argv[1]))
