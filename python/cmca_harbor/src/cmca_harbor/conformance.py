"""Conformance runs (SPEC 9.6): engine configs, Harbor commands, checks, capability files.

    python -m cmca_harbor.conformance tasks
    python -m cmca_harbor.conformance plan --harness pi --version 1.0.3 --model anthropic/<id> --build <dir> --out <dir>
    python -m cmca_harbor.conformance report --harness pi --version 1.0.3 --jobs <dir> [--gap empty:fs.write=<reason>]
"""

import argparse
import base64
import json
import math
import re
import shlex
import shutil
import sys
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cmca_harbor.common import REPO_ROOT
from cmca_harbor.probes import HEAD, POISON_TOKEN, PROBES, TAIL, write_tasks

DATASET = REPO_ROOT / "datasets/conformance"
CATALOG = REPO_ROOT / "packages/fault-engine/catalog/v1.json"
CATALOG_VERSION = "v1"
RUNS = 3
# SPEC 9.6 check 5; the same budget `bench:decide` measures against.
LATENCY_BUDGET_MS = 150.0
# Types with a native delivery path in M1. `inarg` and `latency` have no
# profile weight (D-0005 item 4); the rest are service-layer only.
TYPES = ("deny", "err", "empty", "trunc", "falsefail", "poison")
PRE_PHASE = {"deny", "err"}
TEXT_TYPES = {"deny", "err", "falsefail"}


@dataclass(frozen=True)
class Harness:
    agent: str
    harness_dir: str
    # Tool names in ATIF trajectories, mapped to capability classes.
    tools: dict[str, str]


HARNESSES = {
    "claude-code": Harness(
        "cmca_harbor:ChaosClaudeCode",
        "cc",
        {"Read": "fs.read", "Write": "fs.write", "Edit": "fs.edit", "Grep": "fs.search", "Glob": "fs.search", "Bash": "shell"},
    ),
    "pi": Harness(
        "cmca_harbor:ChaosPi",
        "pi",
        {"read": "fs.read", "write": "fs.write", "edit": "fs.edit", "grep": "fs.search", "find": "fs.search", "ls": "fs.list", "bash": "shell"},
    ),
    "opencode": Harness(
        "cmca_harbor:ChaosOpenCode",
        "oc",
        {"read": "fs.read", "write": "fs.write", "edit": "fs.edit", "grep": "fs.search", "glob": "fs.search", "list": "fs.list", "bash": "shell"},
    ),
}

CLASSES = tuple(PROBES)


def catalog() -> list[dict[str, Any]]:
    return json.loads(CATALOG.read_text())


def cells(entries: list[dict[str, Any]] | None = None) -> list[tuple[str, str]]:
    """(type, class) pairs that have a catalog payload, in a stable order."""
    entries = catalog() if entries is None else entries
    return [(t, c) for t in TYPES for c in CLASSES if any(e["type"] == t and c in e["applies_to"] for e in entries)]


def probe_profile(fault_type: str, capability: str) -> dict[str, Any]:
    """Every call of the probed class gets the type; other classes get nothing."""
    return {
        "schema": "tt-profile/2",
        "name": "probe",
        "base_rate": 1,
        "max_applied_per_trial": 20,
        "warmup_calls": 0,
        "persistence": {"transient": 1},
        "weights": {fault_type: 1},
        "class_rate_multipliers": {c: (1 if c == capability else 0) for c in (*CLASSES, "mcp")},
    }


def task_chaos(task_dir: Path) -> tuple[dict[str, Any], dict[str, str]]:
    """The task section and variants of an engine config, defaults filled in."""
    raw = tomllib.loads((task_dir / "chaos.toml").read_text())
    poison = [{"match": {}, **p} for p in raw.get("poison", [])]
    task = {
        "schema": raw["schema"],
        "exposure": {"expected_classes": [], **raw.get("exposure", {})},
        "poison": poison,
        "non_idempotent": raw.get("non_idempotent", []),
        "drift": raw.get("drift", []),
        "alternatives": raw.get("alternatives", []),
        "exempt": {"paths": [], **raw.get("exempt", {})},
    }
    variants = {p["variant"]: (task_dir / p["variant"]).read_text() for p in poison}
    return task, variants


def engine_config(harness: str, version: str, fault_type: str, capability: str) -> dict[str, Any]:
    probe = PROBES[capability]
    task, variants = task_chaos(DATASET / probe.task)
    return {
        "schema": "tt-engine/1",
        "seed": "conformance",
        "trial_id": None,
        "task_id": probe.task,
        "attempt": 0,
        "harness": f"{harness}@{version}",
        "layer": "native",
        "workspace_root": "/app",
        "profile": probe_profile(fault_type, capability),
        "parity_set": [fault_type],
        "parity_gaps": [],
        "catalog_version": CATALOG_VERSION,
        "task": task,
        "exempt_paths": [],
        "variants": variants,
    }


def broken_build(build: Path, harness: Harness, out: Path) -> None:
    """The injector layout with a plugin module that throws on load (check 6)."""
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(build, out)
    entry = {"cc": "hooks/register.js", "pi": "index.js", "oc": "index.js"}[harness.harness_dir]
    (out / harness.harness_dir / entry).write_text('throw new Error("unavailable");\n')


def plan(harness: str, version: str, model: str, build: Path, out: Path, jobs: Path, dataset: Path = DATASET) -> list[list[str]]:
    """Writes engine configs and the broken build under `out`; returns Harbor commands."""
    h = HARNESSES[harness]
    commands = []
    by_type: dict[str, list[str]] = {}
    # A class with no mapped tool cannot be exposed; fs.search stays for
    # harnesses that list search tools, so a missing tool is observed, not assumed.
    for t, c in [(t, c) for t, c in cells() if c in h.tools.values()]:
        cfg_dir = out / "configs" / t
        cfg_dir.mkdir(parents=True, exist_ok=True)
        (cfg_dir / f"{PROBES[c].task}.json").write_text(json.dumps(engine_config(harness, version, t, c), indent=2))
        by_type.setdefault(t, []).append(PROBES[c].task)

    def cmd(job: str, tasks: list[str], cfg: Path, bld: Path, attempt: int) -> list[str]:
        argv = ["harbor", "run", "-p", str(dataset), "-a", h.agent, "-m", model, "-k", "1", "-o", str(jobs), "--job-name", job, "-y"]
        for task in tasks:
            argv += ["-i", task]
        for k, v in (("attempt_index", attempt), ("tt_config_dir", cfg), ("tt_build_dir", bld), ("version", version)):
            argv += ["--ak", f"{k}={v}"]
        return argv

    for t, tasks in by_type.items():
        for a in range(RUNS):
            commands.append(cmd(f"conf-{harness}-{t}-a{a}", tasks, out / "configs" / t, build, a))
    broken_build(build, h, out / "broken")
    commands.append(cmd(f"conf-{harness}-crash-a0", [PROBES["shell"].task], out / "configs/deny", out / "broken", 0))
    return commands


def _text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    return "\n".join(p.get("text") or "" for p in content if isinstance(p, dict))


def class_calls(trajectory: dict[str, Any], tools: dict[str, str], capability: str) -> list[tuple[str, str]]:
    """(tool name, observation text) for each call of the class, in order."""
    out = []
    for step in trajectory.get("steps", []):
        results = {r.get("source_call_id"): r for r in ((step.get("observation") or {}).get("results") or [])}
        for call in step.get("tool_calls") or []:
            if tools.get(call.get("function_name")) == capability:
                r = results.get(call.get("tool_call_id"))
                out.append((call["function_name"], _text(r.get("content")) if r else ""))
    return out


_EMPTY_RENDERING = re.compile(r"\bempty\b|no (output|content)|without output", re.I)


def delivered(fault_type: str, text: str, payload: str) -> tuple[bool, bool]:
    """(payload reached the model, harness wording around it is visible)."""
    stripped = text.strip()
    if fault_type in TEXT_TYPES:
        ok = bool(payload) and payload in text
        return ok, ok and stripped != payload
    if fault_type == "empty":
        markers = HEAD in text or TAIL in text
        ok = not markers and (stripped == "" or (len(stripped) < 300 and bool(_EMPTY_RENDERING.search(stripped))))
        return ok, ok and stripped != ""
    if fault_type == "trunc":
        return stripped != "" and TAIL not in text, False
    if fault_type == "poison":
        return POISON_TOKEN in text, False
    raise ValueError(fault_type)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text()) if path.exists() else None


def check_trial(trial: Path, harness: str, fault_type: str, capability: str) -> dict[str, Any]:
    """SPEC 9.6 checks 1, 2, 3, 4 and 5 for one trial directory."""
    h = HARNESSES[harness]
    events = [json.loads(line) for line in (trial / "agent/tt/events.jsonl").read_text().splitlines() if line.strip()] if (
        trial / "agent/tt/events.jsonl"
    ).exists() else []
    applied = [e for e in events if e.get("decision") == "apply" and e.get("type") == fault_type and e.get("capability") == capability]
    calls = class_calls(_read_json(trial / "agent/trajectory.json") or {}, h.tools, capability)
    texts = {e["id"]: e["text"] for e in catalog()}
    result: dict[str, Any] = {"trial": trial.name, "exposed": bool(calls), "tool": calls[0][0] if calls else None}
    result["logged"] = bool(applied)
    if calls and applied:
        ok, attribution = delivered(fault_type, calls[0][1], texts.get(applied[0].get("payload_id"), ""))
    else:
        ok, attribution = False, False
    result["delivered"] = ok
    result["attribution_visible"] = attribution if ok else None
    probe = PROBES[capability]
    if probe.effect_path is None:
        result["side_effect"] = None
    else:
        state = _read_json(trial / "verifier/state.json") or {}
        present = bool(state.get("exists"))
        if present and probe.effect_expect:
            content = base64.b64decode(state.get("content_b64") or "").decode(errors="replace").strip()
            present = content == probe.effect_expect
        result["side_effect"] = present == (fault_type not in PRE_PHASE)
    latencies = [e["latency_ms"] for e in events if isinstance(e.get("latency_ms"), (int, float))]
    result["latency_ok"] = bool(latencies) and max(latencies) <= LATENCY_BUDGET_MS
    result["passed"] = all(result[k] is not False for k in ("logged", "delivered", "side_effect", "latency_ok"))
    return result


def _trials(jobs: Path, job: str) -> list[Path]:
    d = jobs / job
    return sorted(p for p in d.iterdir() if p.is_dir() and (p / "config.json").exists()) if d.exists() else []


def _task_of(trial: Path) -> str:
    return Path(json.loads((trial / "config.json").read_text())["task"]["path"]).name


def _p95(values: list[float]) -> float | None:
    if not values:
        return None
    s = sorted(values)
    return round(s[max(0, math.ceil(0.95 * len(s)) - 1)], 3)


def report(harness: str, version: str, jobs: Path, gaps: dict[tuple[str, str], str]) -> dict[str, Any]:
    """The capability file for one harness version from its conformance jobs."""
    h = HARNESSES[harness]
    task_class = {p.task: c for c, p in PROBES.items()}
    per_cell: dict[tuple[str, str], list[dict[str, Any]]] = {}
    latencies: list[float] = []
    seen_tools: dict[str, str] = {}
    for t in TYPES:
        for a in range(RUNS):
            for trial in _trials(jobs, f"conf-{harness}-{t}-a{a}"):
                c = task_class[_task_of(trial)]
                r = check_trial(trial, harness, t, c)
                per_cell.setdefault((t, c), []).append(r)
                # A call the injector never saw (a tool the harness lacks) is not mapped.
                if r["tool"] and r["logged"]:
                    seen_tools[r["tool"]] = c
                ev = trial / "agent/tt/events.jsonl"
                if ev.exists():
                    latencies += [json.loads(x).get("latency_ms", 0) for x in ev.read_text().splitlines() if x.strip()]

    faults: dict[str, Any] = {}
    parity_gaps = []
    for t in TYPES:
        classes: dict[str, Any] = {}
        for (ct, c), runs in per_cell.items():
            if ct != t:
                continue
            passed = sum(r["passed"] for r in runs)
            cell: dict[str, Any] = {
                "runs": len(runs),
                "runs_passed": passed,
                "exposed": any(r["exposed"] for r in runs),
                "attribution_visible": any(r["attribution_visible"] for r in runs),
            }
            if (t, c) in gaps:
                cell["gap"] = gaps[(t, c)]
                parity_gaps.append({"type": t, "capability": c, "reason": gaps[(t, c)]})
            classes[c] = cell
        exposed = {c: v for c, v in classes.items() if v["exposed"]}
        counted = {c: v for c, v in exposed.items() if "gap" not in v}
        full = [c for c, v in counted.items() if v["runs"] >= RUNS and v["runs_passed"] == v["runs"]]
        supported = bool(counted) and len(full) == len(counted)
        entry: dict[str, Any] = {
            "supported": supported,
            "delivered_as": "tool_result" if supported else None,
            "attribution_visible": any(v["attribution_visible"] for v in counted.values()),
            "runs_passed": min((v["runs_passed"] for v in counted.values()), default=0),
            "classes": classes,
        }
        if not supported:
            failing = sorted(c for c in counted if c not in full)
            entry["reason"] = f"failing classes: {', '.join(failing)}" if failing else "no exposed class"
        faults[t] = entry

    crash = _trials(jobs, f"conf-{harness}-crash-a0")
    crash_behavior = "unknown"
    if crash:
        calls = class_calls(_read_json(crash[0] / "agent/trajectory.json") or {}, h.tools, "shell")
        crash_behavior = "fail_open" if calls and HEAD in calls[0][1] else "fail_closed"

    return {
        "schema": "tt-capabilities/1",
        "harness": harness,
        "version": version,
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tool_map": dict(sorted(seen_tools.items())),
        "faults": faults,
        "parity_set": [t for t in TYPES if faults[t]["supported"]],
        "parity_gaps": parity_gaps,
        "crash_behavior": crash_behavior,
        "injector_p95_ms": _p95(latencies),
    }


# What `report` reads from each trial; copied next to the capability file so
# every number in it traces to a committed artifact (CLAUDE.md rule 4).
EVIDENCE = ("config.json", "result.json", "agent/trajectory.json", "agent/tt/events.jsonl", "verifier/state.json")


def archive(jobs: Path, dest: Path) -> int:
    """Copies the evidence files of every conformance trial under `jobs` to `dest`."""
    copied = 0
    for job in sorted(p for p in jobs.iterdir() if p.is_dir() and p.name.startswith("conf-")):
        for trial in _trials(jobs, job.name):
            for rel in EVIDENCE:
                src = trial / rel
                if src.exists():
                    out = dest / job.name / trial.name / rel
                    out.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(src, out)
                    copied += 1
    return copied


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="cmca_harbor.conformance")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("tasks", help="regenerate datasets/conformance")
    p = sub.add_parser("plan", help="write engine configs and print Harbor commands")
    r = sub.add_parser("report", help="write capabilities/<harness>@<version>.json from job directories")
    for s in (p, r):
        s.add_argument("--harness", required=True, choices=sorted(HARNESSES))
        s.add_argument("--version", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--build", required=True, type=Path, help="built injector layout (bin/ and the harness folder)")
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--jobs", type=Path, default=Path("jobs"))
    p.add_argument("--dataset", type=Path, default=DATASET, help="a copy of datasets/conformance, for example with a local CA added")
    r.add_argument("--jobs", required=True, type=Path)
    r.add_argument("--gap", action="append", default=[], help="type:class=reason, a cell conformance showed undeliverable (D-0017)")
    r.add_argument("--out", type=Path, default=REPO_ROOT / "capabilities")
    r.add_argument("--evidence", type=Path, default=REPO_ROOT / "results/conformance", help="where the trial evidence is copied")
    args = ap.parse_args(argv)

    if args.cmd == "tasks":
        for d in write_tasks(REPO_ROOT):
            print(d.relative_to(REPO_ROOT))
        return 0
    if args.cmd == "plan":
        for argv_ in plan(args.harness, args.version, args.model, args.build.resolve(), args.out.resolve(), args.jobs, args.dataset.resolve()):
            print(shlex.join(argv_))
        return 0
    gaps = {}
    for g in args.gap:
        cell, _, reason = g.partition("=")
        t, _, c = cell.partition(":")
        if (t, c) not in cells() or not reason:
            ap.error(f"--gap {g!r}: expected type:class=reason for a cataloged cell")
        gaps[(t, c)] = reason
    caps = report(args.harness, args.version, args.jobs, gaps)
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"{args.harness}@{args.version}.json"
    path.write_text(json.dumps(caps, indent=2) + "\n")
    print(path)
    print(f"{archive(args.jobs, args.evidence / f'{args.harness}@{args.version}')} evidence files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
