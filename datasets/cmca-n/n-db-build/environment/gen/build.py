"""Builds the /app tree: the project files, the 2.0 seeds and the 1.6.0 release database.

Usage: python3 build.py OUT_DIR [--seed N] [--specimens N] [--all-codes]
"""
import argparse
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))

import collection  # noqa: E402

SEED = 31415
SPECIMENS = 1400
# The visible collection uses four of the five documented basis codes.
CODES = [("PS", 72), ("LS", 8), ("IM", 8), ("TS", 12)]
ALL_CODES = CODES + [("SD", 6)]
FIXED_MTIME = 1767225600  # 2026-01-01T00:00:00Z
MARKER = b"canary " + b"GUID"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--specimens", type=int, default=SPECIMENS)
    ap.add_argument("--all-codes", action="store_true")
    args = ap.parse_args(argv)
    out = Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(HERE / "project", out, ignore=shutil.ignore_patterns("__pycache__"))
    # The verifier's copy of this generator carries a marker line in every project file; drop it
    # before anything (migration checksums in particular) depends on the bytes.
    for p in sorted(out.rglob("*")):
        if p.is_file():
            lines = p.read_bytes().split(b"\n")
            kept = [ln for ln in lines if MARKER not in ln]
            if len(kept) != len(lines):
                p.write_bytes(b"\n".join(kept))
    col = collection.model(args.seed, args.specimens, ALL_CODES if args.all_codes else CODES)
    collection.write_seeds(col, out / "seeds")
    collection.write_release(col, out, out / "releases/1.6.0/herbarium.sqlite")
    shutil.rmtree(out / "tools/__pycache__", ignore_errors=True)
    for p in sorted(out.rglob("*")):
        rel = p.relative_to(out).as_posix()
        if p.is_file():
            p.chmod(0o755 if rel == "tools/stratum.py" else 0o644)
        else:
            p.chmod(0o755)
    for p in sorted(out.rglob("*"), reverse=True):
        os.utime(p, (FIXED_MTIME, FIXED_MTIME))
    os.utime(out, (FIXED_MTIME, FIXED_MTIME))


if __name__ == "__main__":
    main()
