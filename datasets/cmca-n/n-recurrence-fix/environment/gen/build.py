"""Builds the /app tree: the agenda package, docs, tools, tests and the data directory.

Usage: python3 build.py OUT_DIR

The output depends only on SEED and the files next to this script.
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bugs  # noqa: E402
import datagen  # noqa: E402

SEED = 52
# Reviewed documents are kept only where the package with the visible-test
# fixes alone already agrees with the rules.
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
    subprocess.run([sys.executable, "-B", "-m", "agenda", "run", "--data", str(data), "--out", str(out)], cwd=package.parent, check=True, capture_output=True)
    return {p.stem: p.read_text(encoding="utf-8") for p in sorted((out / "events").glob("*.json"))}


def build(out: Path) -> None:
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"{out} is not empty")
    out.mkdir(parents=True, exist_ok=True)
    copy_tree(HERE / "src", out)
    datagen.generate(out / "data", SEED)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        copy_tree(HERE / "src" / "agenda", td / "ref" / "agenda")
        copy_tree(HERE / "src" / "agenda", td / "part" / "agenda")
        bugs.apply(td / "part" / "agenda", REVIEW_BUGS)
        ref = run_package(td / "ref" / "agenda", out / "data", td / "ref-out")
        part = run_package(td / "part" / "agenda", out / "data", td / "part-out")
        # Each X entry must show on exactly one event of the visible data;
        # held-out data carries the rest.
        for bug_id in [b for b in bugs.ALL if b.startswith("X")]:
            copy_tree(HERE / "src" / "agenda", td / bug_id / "agenda")
            bugs.apply(td / bug_id / "agenda", [bug_id])
            got = run_package(td / bug_id / "agenda", out / "data", td / f"{bug_id}-out")
            hit = sorted(uid for uid in set(ref) | set(got) if ref.get(uid) != got.get(uid))
            if len(hit) != 1:
                raise SystemExit(f"{bug_id} shows on {len(hit)} visible events, expected 1: {hit[:5]}")
    for uid, text in sorted(ref.items()):
        if part.get(uid) == text:
            dst = out / "tests" / "expected" / "events" / f"{uid}.json"
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(text, encoding="utf-8")
    bugs.apply(out / "agenda", bugs.ALL)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    build(Path(sys.argv[1]))
