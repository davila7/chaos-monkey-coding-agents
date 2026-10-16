"""Build the sdist with the in-tree backend: python tools/build_sdist.py OUT_DIR

Run from the repository root. pip does not build sdists, so this calls the
backend's build_sdist function directly, the way build frontends do.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    if len(sys.argv) != 2:
        sys.stderr.write("usage: python tools/build_sdist.py OUT_DIR\n")
        return 2
    out = os.path.abspath(sys.argv[1])
    os.chdir(ROOT)
    sys.path.insert(0, os.path.join(ROOT, "backend"))
    import kiln

    try:
        name = kiln.build_sdist(out)
    except kiln.KilnError as exc:
        sys.stderr.write(f"kiln: error: {exc}\n")
        return 1
    print(os.path.join(out, name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
