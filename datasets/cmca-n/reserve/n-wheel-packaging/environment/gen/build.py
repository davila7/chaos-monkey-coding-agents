"""Builds the /app tree: the tidecalc repository with its build backend, docs,
tests and station data.

Usage: python3 build.py OUT_DIR

The output depends only on SEED and the files next to this script.
"""

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True

import stations  # noqa: E402

SEED = 30417
PER_REGION = 18


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
            shutil.copymode(p, dst / rel)


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    copy_tree(HERE / "tree", out)
    copy_tree(HERE / "text", out)
    pkg = out / "src" / "tidecalc"
    (pkg / "py.typed").write_text("", encoding="utf-8")
    rows = stations.make_stations(SEED, pkg / "data", PER_REGION)
    # Files that sit in the source tree but are not part of the package.
    south = next(r[0] for r in rows if r[2] == "south")
    backup = json.loads((pkg / "data" / "stations" / "south" / f"{south}.json").read_text(encoding="utf-8"))
    backup["z0"] = round(backup["z0"] - 0.07, 2)
    (pkg / "data" / "stations" / "south" / f"{south}.json~").write_text(json.dumps(backup, indent=2) + "\n", encoding="utf-8")
    (pkg / "data" / "stations" / "west" / "Thumbs.db").write_bytes(bytes([0xD0, 0xCF, 0x11, 0xE0, 0xA1, 0xB1, 0x1A, 0xE1]) + bytes(range(256)) * 2)
    (pkg / "locales" / ".DS_Store").write_bytes(b"\x00\x00\x00\x01Bud1" + bytes(120))
    (pkg / "data" / "SOURCES.txt").write_text(
        "Harmonic constants were derived from the hourly observations in raw/ with\n"
        "tools that live outside this repository. Ask the data team before editing\n"
        "a station file by hand.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
