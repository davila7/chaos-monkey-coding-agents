"""Counts the shapes on which the copies of the access checks in n-access-rules disagree, in the visible samples and the held-out workspaces.

Usage: python3 shapes.py TASK_DIR
Builds the shipped tree (environment/gen/build.py) and the held-out data
(tests/heldout.py) into temporary folders and prints one row per shape.
"""

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def rows(folder: Path, name: str) -> list:
    with (folder / name).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def workspace_shapes(folder: Path) -> dict:
    users = {u["user"]: u for u in rows(folder, "users.csv")}
    docs = rows(folder, "docs.csv")
    grants = rows(folder, "grants.csv")
    dels = rows(folder, "delegations.csv")
    folded = lambda u: users[u]["role"].strip().lower() if u in users else None  # noqa: E731
    sources = {d["from_user"] for d in dels}
    return {
        "role typed other than lower case without spaces": sum(u["role"] != u["role"].strip().lower() for u in users.values()),
        "user without a team": sum(u["team"] == "" for u in users.values()),
        "team document without a team": sum(d["level"] == "team" and d["team"] == "" for d in docs),
        "suspended account with an until day": sum(u["status"] == "suspended" and u["suspended_until"] != "" for u in users.values()),
        "grant on every document from an admin as written": sum(g["doc"] == "*" and g["granted_by"] in users and users[g["granted_by"]]["role"] == "admin" for g in grants),
        "grant on every document from an admin only when folded": sum(g["doc"] == "*" and folded(g["granted_by"]) == "admin" and users[g["granted_by"]]["role"] != "admin" for g in grants),
        "grant on every document from a non-admin or unknown granter": sum(g["doc"] == "*" and folded(g["granted_by"]) != "admin" for g in grants),
        "delegation from an admin or an editor": sum(folded(d["from_user"]) in ("admin", "editor") for d in dels),
        "delegation from a suspended account": sum(d["from_user"] in users and users[d["from_user"]]["status"] == "suspended" for d in dels),
        "delegation whose delegate also lends (a chain)": sum(d["to_user"] in sources and d["to_user"] != d["from_user"] for d in dels),
        "delegation to oneself or from an unknown user": sum(d["from_user"] == d["to_user"] or d["from_user"] not in users for d in dels),
    }


def command_shapes(root: Path, cmds: list) -> dict:
    ends, days = {}, {}
    for args in cmds:
        ws = root / args[1]
        if args[1] in ends or not (ws / "users.csv").is_file():
            continue
        try:
            ends[args[1]] = {r["until"] for r in rows(ws, "grants.csv") + rows(ws, "delegations.csv") if r["until"]}
            days[args[1]] = {u["user"]: u["suspended_until"] for u in rows(ws, "users.csv") if u["status"] == "suspended"}
        except (KeyError, OSError):
            continue
    at_end = on_day = 0
    for args in cmds:
        if args[1] not in ends or "--at" not in args:
            continue
        at = args[args.index("--at") + 1]
        user = args[args.index("--as") + 1]
        at_end += at in ends[args[1]]
        on_day += days[args[1]].get(user) == at[:10]
    return {"command at the until minute of a grant or delegation": at_end, "command by a suspended account on its until day": on_day}


def main() -> None:
    task = Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory() as tmp:
        app, held = Path(tmp) / "app", Path(tmp) / "held"
        subprocess.run([sys.executable, str(task / "environment/gen/build.py"), str(app)], check=True)
        sys.path.insert(0, str(task / "tests"))
        import heldout

        held.mkdir()
        cmds, points = heldout.make(held)
        visible = [workspace_shapes(p) for p in sorted((app / "samples").iterdir())]
        hidden = [workspace_shapes(held / name) for name in points]
        index = json.loads((app / "tests/expected/index.json").read_text())
        vis_cmds = command_shapes(app, [c["args"] for c in index])
        held_cmds = command_shapes(held, cmds)
        print(f"{'Shape':<62} {'Visible':>8} {'Held-out':>9}")
        for key in visible[0]:
            print(f"{key:<62} {sum(v[key] for v in visible):>8} {sum(h[key] for h in hidden):>9}")
        for key in vis_cmds:
            print(f"{key:<62} {vis_cmds[key]:>8} {held_cmds[key]:>9}")
        print(f"{'commands':<62} {len(index):>8} {len(cmds):>9}")


if __name__ == "__main__":
    main()
