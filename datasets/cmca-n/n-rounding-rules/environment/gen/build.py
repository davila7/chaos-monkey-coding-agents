"""Builds the /app tree: the meterbill package, its tests, docs, samples and reviewed outputs.

Usage: python3 build.py OUT_DIR

The output depends only on SEED and the files next to this script.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True

SEED = 52817
ACCOUNTS = 9
TIE_BAND = {1007}

QUOTES = [
    ("quote-home-2", ["quote", "home-2", "250.5", "30"]),
    ("quote-flex-ch", ["quote", "flex-ch", "1234.5", "91", "--format", "json"]),
    ("quote-villa-se", ["quote", "villa-se", "812.3", "30"]),
    ("quote-uk-std", ["quote", "uk-std", "0", "31"]),
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
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONDONTWRITEBYTECODE": "1", "LANG": "C.UTF-8"}
    r = subprocess.run([sys.executable, "-m", "meterbill", *args], cwd=out, env=env, capture_output=True, text=True, check=True)
    return r.stdout


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    copy_tree(HERE / "src", out)
    sys.path.insert(0, str(out))
    sys.path.insert(0, str(HERE))
    import datagen

    docs = datagen.write(SEED, ACCOUNTS, TIE_BAND, out / "samples" / "accounts")
    expected = out / "tests" / "expected"
    expected.mkdir(parents=True, exist_ok=True)
    for d in docs:
        name = d["account"].lower()
        path = f"samples/accounts/{name}.json"
        (expected / f"bill-{name}.txt").write_text(cli(out, ["bill", path]))
        (expected / f"bill-{name}.json").write_text(cli(out, ["bill", path, "--format", "json"]))
    (expected / "bill-a-1001.csv").write_text(cli(out, ["bill", "samples/accounts/a-1001.json", "--format", "csv"]))
    (expected / "batch.txt").write_text(cli(out, ["batch", "samples/accounts"]))
    (expected / "batch.csv").write_text(cli(out, ["batch", "samples/accounts", "--format", "csv", "--workers", "2"]))
    for name, args in QUOTES:
        suffix = ".json" if "json" in args else ".txt"
        (expected / f"{name}{suffix}").write_text(cli(out, args))
    (expected / "tariffs.txt").write_text(cli(out, ["tariffs"]))
    for p in out.rglob("__pycache__"):
        shutil.rmtree(p)


if __name__ == "__main__":
    main()
