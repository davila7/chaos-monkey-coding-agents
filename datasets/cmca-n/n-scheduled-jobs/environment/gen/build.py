"""Builds the /app tree: the spokehouse package, its tests, tools and docs, the
feeds, the snapshots, and the scheduler, operator, deploy and audit logs.

Usage: python3 build.py OUT_DIR

The logs and snapshots come from running schedule.json (plan.py wrote it)
with tools/sched.py: runs that start before the 4.2.0 deploy run on the
shipped package with D1 and version 4.1.2, the rest on the shipped package.
The audits compare the state with the books, which are the same schedule run
on the correct package. The output depends only on the files next to this
script.
"""

import importlib
import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bugs  # noqa: E402

VERSION = "4.2.0"
OLD_VERSION = "4.1.2"


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


def package_tree(dst: Path, ids, version: str = VERSION) -> Path:
    """A copy of the package with the named edits; returns the package directory."""
    pkg = dst / "spokehouse"
    copy_tree(HERE / "src" / "spokehouse", pkg)
    bugs.apply(pkg, ids)
    init = pkg / "__init__.py"
    init.write_text(init.read_text(encoding="utf-8").replace(f'__version__ = "{VERSION}"', f'__version__ = "{version}"'), encoding="utf-8")
    return pkg


def load_package(pkg_dir: Path, alias: str):
    """Imports a package directory under another name, so several variants can live in one process."""
    spec = importlib.util.spec_from_file_location(alias, pkg_dir / "__init__.py", submodule_search_locations=[str(pkg_dir)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[alias] = module
    spec.loader.exec_module(module)
    for name in ("errors", "timeutil", "settings", "fares", "feeds", "store", "ops", "jobs"):
        importlib.import_module(f"{alias}.{name}")
    return module


def sched_module():
    spec = importlib.util.spec_from_file_location("spokehouse_sched", HERE / "src" / "tools" / "sched.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def schedule() -> dict:
    return json.loads((HERE / "schedule.json").read_text(encoding="utf-8"))


def seed_root(root: Path, plan: dict, pkg) -> None:
    """Writes the feeds and the first state of a schedule under root."""
    for rel, text in plan["feeds"].items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    (root / "var" / "snapshots").mkdir(parents=True, exist_ok=True)
    first = plan["initial"]
    text = pkg.store.render(first)
    (root / "var" / "state.json").write_text(text, encoding="utf-8")
    (root / "var" / "snapshots" / pkg.store.snapshot_name(first["meta"])).write_text(text, encoding="utf-8")


def execute(root: Path, plan: dict, phases) -> list[tuple[str, str]]:
    """Runs the schedule under root; phases is a list of (package, runs) run in order."""
    sched = sched_module()
    lines: list[tuple[str, str]] = []
    for pkg, runs in phases:
        sched.run_timeline(pkg, runs, root, lambda channel, line: lines.append((channel, line)))
    return lines


def history(root: Path) -> list[dict]:
    """Every snapshot under root in the order it was written."""
    out = []
    for p in (root / "var" / "snapshots").glob("*.json"):
        state = json.loads(p.read_text(encoding="utf-8"))
        out.append({"name": p.name, "state": state})
    return sorted(out, key=lambda s: (s["state"]["meta"]["at"], s["state"]["meta"]["rev"]))


def latest_before(hist: list[dict], at: str) -> dict:
    return [s for s in hist if s["state"]["meta"]["at"] <= at][-1]


def audit(state: dict, books: dict) -> list[str]:
    out = []
    for dock in sorted(set(state["docks"]) | set(books["docks"])):
        a, b = state["docks"].get(dock, {}).get("bikes"), books["docks"].get(dock, {}).get("bikes")
        if a != b:
            out.append(f"mismatch docks.{dock}.bikes state={a} books={b}")
    for member in sorted(set(state["members"]) | set(books["members"])):
        for field in ("balance_cents", "trips"):
            a, b = state["members"].get(member, {}).get(field), books["members"].get(member, {}).get(field)
            if a != b:
                out.append(f"mismatch members.{member}.{field} state={a} books={b}")
    for hold in sorted(set(state["holds"]) | set(books["holds"])):
        a, b = hold in state["holds"], hold in books["holds"]
        if a != b:
            out.append(f"mismatch holds.{hold} state={'present' if a else 'absent'} books={'present' if b else 'absent'}")
    return out


def run_world(work: Path) -> dict:
    """Runs the schedule on the shipped history and on the books; returns both roots and the log lines."""
    plan = schedule()
    shipped = load_package(package_tree(work / "pkg-shipped", bugs.SHIPPED), "sh_shipped")
    old = load_package(package_tree(work / "pkg-old", (*bugs.SHIPPED, "D1"), OLD_VERSION), "sh_old")
    correct = load_package(package_tree(work / "pkg-correct", ()), "sh_correct")
    deploy = plan["deploy"]["at"]
    before = [r for r in plan["runs"] if r["start"] < deploy]
    after = [r for r in plan["runs"] if r["start"] >= deploy]
    if any(r["end"] >= deploy for r in before):
        raise SystemExit("a run straddles the deploy")
    app = work / "app"
    seed_root(app, plan, shipped)
    lines = execute(app, plan, [(old, before), (shipped, after)])
    books = work / "books"
    seed_root(books, plan, correct)
    execute(books, plan, [(correct, plan["runs"])])
    return {"plan": plan, "app": app, "books": books, "lines": lines}


def write_logs(out: Path, world: dict) -> None:
    plan = world["plan"]
    sched = {}
    ops = []
    for channel, line in world["lines"]:
        if channel == "ops":
            ops.append(line)
        else:
            sched.setdefault(line[:10], []).append(line)
    (out / "logs" / "sched").mkdir(parents=True, exist_ok=True)
    for day, lines in sorted(sched.items()):
        (out / "logs" / "sched" / f"{day}.log").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "logs" / "ops.log").write_text("\n".join(plan["ops_header"] + ops) + "\n", encoding="utf-8")
    (out / "logs" / "deploy.log").write_text("\n".join(plan["deploy"]["log"]) + "\n", encoding="utf-8")
    shipped_hist, books_hist = history(world["app"]), history(world["books"])
    (out / "logs" / "audit").mkdir(parents=True, exist_ok=True)
    for at in plan["audits"]:
        state = latest_before(shipped_hist, at)
        books = latest_before(books_hist, at)
        diff = audit(state["state"], books["state"])
        body = [f"audit {at}", f"state: {state['name']}", f"books: upstream ledger close at {at}", *diff, f"{len(diff)} fields differ"]
        name = at.replace("-", "").replace(":", "")
        (out / "logs" / "audit" / f"{name}.txt").write_text("\n".join(body) + "\n", encoding="utf-8")


def main() -> int:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        world = run_world(work)
        package_tree(out, bugs.SHIPPED)
        for name in ("tools", "tests", "docs"):
            copy_tree(HERE / "src" / name, out / name)
        copy_tree(world["app"] / "feeds", out / "feeds")
        copy_tree(world["app"] / "var", out / "var")
        write_logs(out, world)
    return 0


if __name__ == "__main__":
    sys.exit(main())
