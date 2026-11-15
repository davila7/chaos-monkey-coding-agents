"""Builds the /app tree: the shelfmark package, its tests, tools and docs, the
configuration history, and the access, service and upstream logs.

Usage: python3 build.py OUT_DIR

The traffic comes from world.PUBLIC. Every `started` line before the 2.4.0
deploy runs release 2.3.1 (the package with D1), the later ones the shipped
package (the B entries of bugs.py); the access log records what each
request got. The output depends only on the files next to this script.
"""

import importlib
import importlib.util
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bugs  # noqa: E402
import world  # noqa: E402

VERSION = "2.4.0"
OLD_VERSION = "2.3.1"
DEPLOY = "2027-05-03T14:00:01+00:00"
HOUR = 3_600_000
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
    pkg = dst / "shelfmark"
    copy_tree(HERE / "src" / "shelfmark", pkg)
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
    for name in ("errors", "routes", "config", "locale", "keys", "cache", "service"):
        importlib.import_module(f"{alias}.{name}")
    return module


def items(drawn: dict) -> list[tuple]:
    """(ms, order, kind, fields) as tools/replay.py builds them from the logs."""
    out = []
    for at, line in drawn["events"]:
        if line.startswith("started"):
            out.append((at, 0, "started", {"config": line.split("config=")[1]}))
        elif line == "stopping":
            out.append((at, 0, "stopping", {}))
        elif line.startswith("config reload"):
            out.append((at, 0, "reload", {"config": f"r{int(line.split('rev=')[1]):03d}"}))
        elif line == "cache flush":
            out.append((at, 0, "flush", {}))
    for r in drawn["requests"]:
        out.append((r["at"], 1, "request", r))
    return sorted(out, key=lambda item: (item[0], item[1]))


def play(timeline: list[tuple], release, configs: dict[str, str], start: int = 0, marks=()) -> dict:
    """Runs a timeline from index start; release(ms) gives the package a `started` line runs.

    Returns the result per request id, the entries removed by each flush and
    the entries held at each mark."""
    marks = sorted(marks)
    held, flushed, results = {}, {}, {}
    svc = pkg = None
    mi = 0
    for at, _, kind, fields in timeline[start:]:
        while mi < len(marks) and marks[mi] <= at:
            held[marks[mi]] = len(svc.cache) if svc else 0
            mi += 1
        if kind == "started":
            pkg = release(at)
            svc = pkg.service.Service(pkg.config.parse(configs[fields["config"]]))
        elif kind == "stopping":
            svc = None
        elif kind == "reload":
            svc.reload(pkg.config.parse(configs[fields["config"]]))
        elif kind == "flush":
            flushed[at] = svc.flush()
        else:
            if svc is None:
                raise SystemExit(f"{fields['id']}: request while stopped")
            results[fields["id"]] = svc.handle(fields["method"], fields["target"], fields["lang"], at)
    for m in marks[mi:]:
        held[m] = len(svc.cache) if svc else 0
    return {"results": results, "flushed": flushed, "held": held}


def latency(req: dict, result: str, incident: tuple[int, int]) -> int:
    r = req["r"]
    if result != "miss":
        return 1 + r % 4
    base, spread = {"books": (40, 90), "search": (90, 180), "authors": (30, 70)}[req["route"]]
    ms = base + (r * spread) // 1000
    if incident[0] <= req["at"] < incident[1]:
        ms *= 6 + r % 5
    return ms


def configs_of(root: Path) -> dict[str, str]:
    return {p.stem: p.read_text(encoding="utf-8") for p in sorted((root / "config" / "history").glob("r*.toml"))}


def run_world(work: Path, spec: dict = world.PUBLIC, shipped_ids=bugs.SHIPPED, old_ids=bugs.OLD, deploy: str = DEPLOY, configs=None, marks=True) -> dict:
    """Draws a spec and runs it: the old release before deploy, the shipped one after."""
    drawn = world.draw(spec)
    timeline = items(drawn)
    _loaded[0] += 1
    shipped = load_package(package_tree(work / f"pkg-shipped-{_loaded[0]}", shipped_ids), f"sm_shipped_{_loaded[0]}")
    old = load_package(package_tree(work / f"pkg-old-{_loaded[0]}", old_ids, OLD_VERSION), f"sm_old_{_loaded[0]}")
    cut = world.to_ms(deploy)
    configs = configs or configs_of(HERE / "src")
    start, end = world.to_ms(spec["start"]), world.to_ms(spec["end"])
    hours = list(range(start + HOUR, end + 1, HOUR)) if marks else []
    played = play(timeline, lambda at: shipped if at >= cut else old, configs, marks=hours)
    return {"spec": spec, "drawn": drawn, "timeline": timeline, "played": played, "hours": hours, "configs": configs, "cut": cut}


def percentile(values: list[int], pct: int) -> int:
    values = sorted(values)
    return values[max(0, (pct * len(values) + 99) // 100 - 1)]


def write_logs(out: Path, w: dict) -> None:
    spec, drawn, played = w["spec"], w["drawn"], w["played"]
    incident = tuple(world.to_ms(t) for t in spec["incident"]) if spec.get("incident") else (0, 0)
    results = played["results"]
    lines_by_day: dict[str, list[str]] = {}
    lat = {}
    for r in drawn["requests"]:
        res = results[r["id"]]
        lat[r["id"]] = latency(r, res, incident)
        lang = r["lang"] if r["lang"] is not None else "-"
        line = f'{world.stamp(r["at"])} {r["id"]} {r["method"]} {r["target"]} status=200 cache={res} ms={lat[r["id"]]} lang="{lang}"'
        lines_by_day.setdefault(line[:10], []).append(line)
    (out / "logs" / "access").mkdir(parents=True, exist_ok=True)
    for day, lines in sorted(lines_by_day.items()):
        (out / "logs" / "access" / f"{day}.log").write_text("\n".join(lines) + "\n", encoding="utf-8")
    service = []
    for at, line in drawn["events"]:
        if line == "cache flush":
            line = f"cache flush entries={played['flushed'][at]}"
        service.append((at, 1, f"{world.stamp(at)} {line}"))
    for h in w["hours"]:
        window = [r for r in drawn["requests"] if h - HOUR <= r["at"] < h and results[r["id"]] != "-"]
        hits = sum(1 for r in window if results[r["id"]] == "hit")
        rate = (hits * 100 + len(window) // 2) // len(window) if window else 0
        times = [lat[r["id"]] for r in window]
        p50, p95 = (percentile(times, 50), percentile(times, 95)) if window else (0, 0)
        label = world.stamp(h - HOUR)[:13]
        service.append((h, 0, f"{world.stamp(h)} stats hour={label} requests={len(window)} hits={hits} hit_rate={rate // 100}.{rate % 100:02d} p50_ms={p50} p95_ms={p95} entries={played['held'][h]}"))
    service.sort()
    (out / "logs" / "service.log").write_text("\n".join(line for _, _, line in service) + "\n", encoding="utf-8")
    if spec.get("incident"):
        d = world.Draw(spec["seed"] + 1)
        up = []
        t = world.to_ms(spec["start"])
        while t < world.to_ms(spec["end"]):
            bad = incident[0] <= t < incident[1]
            p95 = 1300 + d.below(800) if bad else 180 + d.below(90)
            errors = d.below(9) if bad else 0
            up.append(f"{world.stamp(t)[:19]}Z catalog-db p95_ms={p95} errors={errors} state={'degraded' if bad else 'ok'}")
            t += 300_000
        (out / "logs" / "upstream.log").write_text("\n".join(up) + "\n", encoding="utf-8")


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
