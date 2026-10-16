"""Builds the /app tree: the frontdoor package, docs, tests, configurations and traces.

Usage: python3 build.py OUT_DIR

The output depends only on SEED and the files next to this script.
"""

import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import tracegen  # noqa: E402

SEED = 2701


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


def build(out: Path) -> None:
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"{out} is not empty")
    out.mkdir(parents=True, exist_ok=True)
    copy_tree(HERE / "src", out)
    tracegen.generate(out, SEED)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    build(Path(sys.argv[1]))
