"""Builds the /app tree: the docshelf package, its tests, docs, sample workspaces and reviewed outputs.

Usage: python3 build.py OUT_DIR

The output depends only on SEED and the files next to this script.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True

SEED = 52817
SAMPLES = [
    ("north", ["ops", "legal", "design"], datetime(2026, 5, 4, 0, 0)),
    ("south", ["finance", "sales", "ops", "research"], datetime(2026, 6, 8, 0, 0)),
]


def cli(cwd: Path, args: list) -> subprocess.CompletedProcess:
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONDONTWRITEBYTECODE": "1", "LANG": "C.UTF-8", "PYTHONPATH": str(cwd)}
    return subprocess.run([sys.executable, "-m", "docshelf", *args], cwd=cwd, env=env, capture_output=True, text=True)


def reviewed(data: dict, folder: str, start: datetime) -> list:
    """(name, args, changes the workspace) for one sample."""
    users = [u[0] for u in data["users"]]
    admin = users[0]
    active = [u for u in data["users"] if u[3] == "active"]
    viewer = next(u[0] for u in active[1:] if u[1] == "viewer")
    editor = next(u[0] for u in active[1:] if u[1] == "editor")
    suspended = next(u[0] for u in data["users"] if u[3] == "suspended")
    delegate = data["delegations"][0][1] if data["delegations"] else viewer
    docs = [d[0] for d in data["docs"]]
    private = [d[0] for d in data["docs"] if d[4] == "private"]
    team = [d for d in data["docs"] if d[4] == "team"]
    owned = next(d for d in data["docs"] if d[2] == editor)
    at = (start.replace(day=start.day + 3, hour=10, minute=15)).strftime("%Y-%m-%dT%H:%M")
    late = (start.replace(day=start.day + 5, hour=16, minute=45)).strftime("%Y-%m-%dT%H:%M")
    ws = f"samples/{folder}"
    out = [
        (f"list-{folder}-{admin}", ["list", ws, "--as", admin, "--at", at], False),
        (f"list-{folder}-{viewer}", ["list", ws, "--as", viewer, "--at", at], False),
        (f"list-{folder}-{viewer}-csv", ["list", ws, "--as", viewer, "--at", late, "--format", "csv"], False),
        (f"list-{folder}-{delegate}-json", ["list", ws, "--as", delegate, "--at", at, "--format", "json"], False),
        (f"list-{folder}-{suspended}", ["list", ws, "--as", suspended, "--at", at], False),
        (f"audit-{folder}", ["audit", ws, "--as", admin, "--at", at], False),
        (f"audit-{folder}-csv", ["audit", ws, "--as", admin, "--at", late, "--format", "csv"], False),
        (f"audit-{folder}-denied", ["audit", ws, "--as", viewer, "--at", at], False),
        (f"show-{folder}-{team[0][0]}", ["show", ws, team[0][0], "--as", editor, "--at", at], False),
        (f"show-{folder}-{private[0]}", ["show", ws, private[0], "--as", viewer, "--at", at], False),
        (f"show-{folder}-{docs[1]}", ["show", ws, docs[1], "--as", delegate, "--at", late], False),
        (f"edit-{folder}-owner", ["edit", ws, owned[0], "--title", "Renamed by owner", "--as", editor, "--at", at], True),
        (f"edit-{folder}-viewer", ["edit", ws, private[-1], "--title", "Not allowed", "--as", viewer, "--at", at], True),
        (f"share-{folder}-owner", ["share", ws, owned[0], viewer, "--right", "write", "--until", late, "--as", editor, "--at", at], True),
        (f"share-{folder}-suspended", ["share", ws, docs[0], viewer, "--as", suspended, "--at", at], True),
        (f"delete-{folder}-admin", ["delete", ws, private[0], "--as", admin, "--at", late], True),
    ]
    return [(f"{i:02d}-{name}", args, changes) for i, (name, args, changes) in enumerate(out)]


def run_reviewed(out: Path, args: list, changes: bool) -> dict:
    if not changes:
        r = cli(out, args)
        return {"code": r.returncode, "stdout": r.stdout, "stderr": r.stderr}
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        shutil.copytree(out / "docshelf", work / "docshelf")
        shutil.copytree(out / args[1], work / args[1])
        r = cli(work, args)
        files = {p.name: p.read_text(encoding="utf-8") for p in sorted((work / args[1]).iterdir())}
    return {"code": r.returncode, "stdout": r.stdout, "stderr": r.stderr, "files": files}


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
    sys.path.insert(0, str(HERE))
    import datagen

    expected = out / "tests" / "expected"
    expected.mkdir(parents=True, exist_ok=True)
    plans = []
    for i, (folder, teams, start) in enumerate(SAMPLES):
        data = datagen.make(SEED + i, teams, start)
        datagen.write_workspace(out / "samples" / folder, data)
        plans += reviewed(data, folder, start)
    index = []
    for name, args, changes in plans:
        result = run_reviewed(out, args, changes)
        (expected / (name + ".json")).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        index.append({"name": name, "args": args, "changes": changes})
    (expected / "index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    for p in out.rglob("__pycache__"):
        shutil.rmtree(p)


if __name__ == "__main__":
    main()
