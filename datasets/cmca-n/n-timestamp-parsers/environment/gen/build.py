"""Builds the /app tree: the deskstats package, its tests, docs, sample site folders and reviewed outputs.

Usage: python3 build.py OUT_DIR

The output depends only on SEED and the files next to this script.
"""

import os
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True

SEED = 61349
SITES = [
    ("north", "North desk", "+01:00", date(2026, 3, 2), 7),
    ("south", "South desk", "-05:00", date(2026, 3, 9), 6),
]
REVIEWED = [
    ("daily", []), ("daily", ["--format", "csv"]), ("daily", ["--format", "json"]),
    ("tickets", []), ("tickets", ["--format", "json"]),
    ("calls", []), ("chats", []), ("chats", ["--format", "json"]),
    ("roster", []), ("roster", ["--format", "csv"]),
]
WINDOWED = [
    ("daily-north-mar03-mar05.txt", ["daily", "samples/north", "--since", "2026-03-03", "--until", "2026-03-05"]),
    ("tickets-south-until-mar12.csv", ["tickets", "samples/south", "--until", "2026-03-12", "--format", "csv"]),
    ("calls-north-since-mar06.txt", ["calls", "samples/north", "--since", "2026-03-06"]),
]


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


def cli(out: Path, args: list) -> str:
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONDONTWRITEBYTECODE": "1", "LANG": "C.UTF-8", "TZ": "UTC"}
    r = subprocess.run([sys.executable, "-m", "deskstats", *args], cwd=out, env=env, capture_output=True, text=True, check=True)
    return r.stdout


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    copy_tree(HERE / "src", out)
    sys.path.insert(0, str(HERE))
    import datagen

    for i, (folder, name, offset, first, days) in enumerate(SITES):
        datagen.write_site(out / "samples" / folder, SEED + i, name, offset, first, days)
    expected = out / "tests" / "expected"
    expected.mkdir(parents=True, exist_ok=True)
    for folder, *_ in SITES:
        for command, extra in REVIEWED:
            suffix = extra[-1] if extra else "txt"
            (expected / f"{command}-{folder}.{suffix}").write_text(cli(out, [command, f"samples/{folder}", *extra]))
    for name, args in WINDOWED:
        (expected / name).write_text(cli(out, args))
    for p in out.rglob("__pycache__"):
        shutil.rmtree(p)


if __name__ == "__main__":
    main()
