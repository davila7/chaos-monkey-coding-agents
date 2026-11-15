"""Builds the /app tree: the quayside package, its tests, tools and docs, the
configuration history, the queue, worker, service and downstream logs, and
the checkpoints.

Usage: python3 build.py OUT_DIR

The traffic comes from world.PUBLIC. Every `started` line before the 4.2.0
deploy runs release 4.1.3 (the package with D1), the later ones the shipped
package (the B entries of bugs.py); the logs record what each run did. The
output depends only on the files next to this script.
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
import world  # noqa: E402

VERSION = "4.2.0"
OLD_VERSION = "4.1.3"
DEPLOY = "2027-06-08T14:00:01+00:00"
HOUR = 3_600_000
MODULES = ("errors", "config", "schema", "dedupe", "retry", "lease", "checkpoint", "broker")
_loaded = [0]


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
    pkg = dst / "quayside"
    copy_tree(HERE / "src" / "quayside", pkg)
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
    for name in MODULES:
        setattr(module, name, importlib.import_module(f"{alias}.{name}"))
    return module


def load_tool(path: Path = HERE / "src" / "tools" / "replay.py"):
    spec = importlib.util.spec_from_file_location("qs_replay_tool", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TOOL = load_tool()


def canonical(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def items_of(drawn: dict) -> list[tuple]:
    """The timeline tools/replay.py reads back from the logs."""
    services = []
    for at, line in drawn["events"]:
        if line.startswith("started"):
            services.append((at, "started", {"config": line.split("config=")[1], "checkpoint": None}))
        elif line == "stopping":
            services.append((at, "stopping", {}))
        elif line.startswith("config reload"):
            services.append((at, "reload", {"config": f"r{int(line.split('rev=')[1]):03d}"}))
    enqueues = [(at, {"id": mid, "type": job, "payload": json.loads(canonical(payload))}) for at, mid, job, _, payload in drawn["messages"]]
    return TOOL.make_items(services, enqueues, drawn["end"])


def configs_of(root: Path) -> dict[str, str]:
    return {p.stem: p.read_text(encoding="utf-8") for p in sorted((root / "config" / "history").glob("r*.toml"))}


def run_world(work: Path, spec: dict = world.PUBLIC, shipped_ids=bugs.SHIPPED, old_ids=bugs.OLD, deploy: str = DEPLOY, configs=None, marks=True) -> dict:
    """Draws a spec and runs it: the old release before deploy, the shipped one after."""
    drawn = world.draw(spec)
    drawn["end"] = world.to_ms(spec["end"])
    items = items_of(drawn)
    _loaded[0] += 1
    shipped = load_package(package_tree(work / f"pkg-shipped-{_loaded[0]}", shipped_ids), f"qs_shipped_{_loaded[0]}")
    old = load_package(package_tree(work / f"pkg-old-{_loaded[0]}", old_ids, OLD_VERSION), f"qs_old_{_loaded[0]}")
    cut = world.to_ms(deploy)
    configs = configs or configs_of(HERE / "src")
    env = TOOL.Downstream(drawn["downstream"])
    start, end = world.to_ms(spec["start"]), world.to_ms(spec["end"])
    hours = list(range(start + HOUR, end + 1, HOUR)) if marks else []
    backlog = {}

    def on_mark(at, eng, state):
        backlog[at] = eng.pending() if eng is not None else len(state["messages"])

    played = TOOL.play(items, lambda at: shipped if at >= cut else old, configs, env, marks=hours, on_mark=on_mark)
    return {"spec": spec, "drawn": drawn, "items": items, "played": played, "hours": hours, "backlog": backlog,
            "configs": configs, "cut": cut, "env": env}


def compact(ms: int) -> str:
    return world.stamp(ms)[:19].replace("-", "").replace(":", "") + "Z"


def write_logs(out: Path, w: dict) -> None:
    drawn, played = w["drawn"], w["played"]
    stamp = world.stamp
    queue: list[tuple] = []
    for at, mid, job, producer, payload in drawn["messages"]:
        queue.append((at, 0, len(queue), f"{stamp(at)} enqueue {mid} {job} producer={producer} {canonical(payload)}"))
    worker = []
    for n, (at, stream, text) in enumerate(played["log"]):
        if stream == "queue":
            queue.append((at, 1, n, f"{stamp(at)} {text}"))
        else:
            worker.append((at, n, f"{stamp(at)} {text}"))
    queue.sort()
    worker.sort()
    by_day: dict[str, list[str]] = {}
    for *_, line in queue:
        by_day.setdefault(line[:10], []).append(line)
    (out / "logs" / "queue").mkdir(parents=True, exist_ok=True)
    for day, lines in sorted(by_day.items()):
        (out / "logs" / "queue" / f"{day}.log").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "logs" / "worker.log").write_text("\n".join(line for *_, line in worker) + "\n", encoding="utf-8")

    (out / "var" / "checkpoints").mkdir(parents=True, exist_ok=True)
    service = []
    last = None
    for at, line in drawn["events"]:
        if line == "stopping":
            last = f"var/checkpoints/{compact(at)}.json"
            (out / last).write_text(json.dumps(played["checkpoints"][at], indent=1, sort_keys=True) + "\n", encoding="utf-8")
            line = f"stopping checkpoint={last}"
        elif line.startswith("started") and last is not None:
            line = f"{line} checkpoint={last}"
        service.append((at, 1, f"{stamp(at)} {line}"))
    outcomes = played["outcomes"]
    enq = sorted(at for at, *_ in drawn["messages"])
    dead_total = 0
    for h in w["hours"]:
        lo = h - HOUR
        enqueued = sum(1 for at in enq if lo <= at < h)
        tally = {"done": 0, "duplicate": 0, "dead": 0}
        for disp, at, _ in outcomes.values():
            if lo <= at < h:
                tally["dead" if disp.startswith("dead-letter") else disp] += 1
        dead_total += tally["dead"]
        service.append((h, 0, f"{stamp(h)} stats hour={stamp(lo)[:13]} enqueued={enqueued} done={tally['done']} duplicate={tally['duplicate']} dead_lettered={tally['dead']} backlog={w['backlog'][h]} dlq={dead_total}"))
    service.sort()
    (out / "logs" / "service.log").write_text("\n".join(line for *_, line in service) + "\n", encoding="utf-8")
    down = [f"{stamp(at)} {svc} state={st}" + (f" retry_after={ra // 1000}s" if st == "throttled" else "") for at, svc, st, ra in sorted(drawn["downstream"], key=lambda c: (c[0], c[1]))]
    (out / "logs" / "downstream.log").write_text("\n".join(down) + "\n", encoding="utf-8")


def main() -> int:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        w = run_world(Path(tmp))
        package_tree(out, bugs.SHIPPED)
        for name in ("tools", "tests", "docs", "config", "logs"):
            copy_tree(HERE / "src" / name, out / name)
        write_logs(out, w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
