"""Builds the /app tree: the quoter package, its tests, docs and sample files.

Usage: python3 build.py OUT_DIR

The output depends only on SEED and the files next to this script.
"""

import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True

import samples  # noqa: E402

SEED = 61907
FILES = 8
ROWS = 160


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
    samples.make_samples(SEED, out / "samples", FILES, ROWS)


if __name__ == "__main__":
    main()
