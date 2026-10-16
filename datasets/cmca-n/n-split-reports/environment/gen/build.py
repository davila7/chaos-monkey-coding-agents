"""Builds the /app tree: the tally package, its tests, docs and sample exports.

Usage: python3 build.py OUT_DIR

The output depends only on SEED and the files next to this script.
"""

import shutil
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import samples  # noqa: E402

SEED = 4242
FILES = 14


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


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    copy_tree(HERE / "src", out)
    samples.make_exports(SEED, out / "samples", FILES, date(2025, 10, 1), 9)


if __name__ == "__main__":
    main()
