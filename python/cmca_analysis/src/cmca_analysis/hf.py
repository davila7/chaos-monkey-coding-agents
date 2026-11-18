"""`python -m cmca_analysis hf --release <dir>`: per-task and per-trial tables for the Hugging Face dataset.

Writes `<release>/hf/tasks.jsonl` (one row per active task) and `<release>/hf/trials.jsonl` (one row per
trial in the release's evidence, the same trials and classification `analyze` used). JSON Lines loads in
the Hub's Dataset Viewer and `datasets.load_dataset` without extra dependencies (D-0050 item 5).
"""

from __future__ import annotations

import argparse
import json
import tomllib
from collections import Counter
from pathlib import Path
from typing import Any

from .analyze import load_configs, mark_superseded
from .classify import analyze_trial
from .ingest import DATASETS, REPO_ROOT, TaskDecl, load_trial, payload_texts, settled_costs, task_decls, trial_dirs
from .metrics import dumps
from .reconcile import reconcile
from .rules import load_rules
from .validate import validate

SCHEMA = "cmca-hf/1"


def task_rows(datasets: tuple[Path, ...] | list[Path], used: set[str]) -> list[dict[str, Any]]:
    rows = []
    for dataset in datasets:
        for toml in sorted(Path(dataset).glob("*/task.toml")):
            d = toml.parent
            meta = tomllib.loads(toml.read_text())
            chaos = tomllib.loads((d / "chaos.toml").read_text()) if (d / "chaos.toml").exists() else {}
            rows.append({
                "task_id": d.name,
                "track": "s" if Path(dataset).name.endswith("-s") else "n",
                "version": meta["task"].get("version"),
                "description": meta["task"].get("description"),
                "instruction": (d / "instruction.md").read_text(),
                "mcp_servers": sorted(s["name"] for s in meta.get("environment", {}).get("mcp_servers", [])),
                "agent_timeout_sec": meta.get("agent", {}).get("timeout_sec"),
                "poison_tools": sorted({p.get("tool") for p in chaos.get("poison", []) if p.get("tool")}),
                "non_idempotent_tools": sorted({x["tool"] for x in chaos.get("non_idempotent", [])}),
                "in_release": d.name in used,
                "path": f"tasks/{Path(dataset).name}/{d.name}",
            })
    return sorted(rows, key=lambda r: (r["track"], r["task_id"]))


def trial_rows(release: str, evidence: list[Path], datasets: tuple[Path, ...] | list[Path], configs_dir: Path) -> list[dict[str, Any]]:
    rules = load_rules()
    decls = task_decls(list(datasets))
    payloads = payload_texts()
    configs = load_configs(configs_dir)
    rows = []
    loaded = []
    for ev in evidence:
        settled = settled_costs(ev)
        for d in trial_dirs(ev):
            t = load_trial(d, ev, decls, settled)
            decl = decls.get(t.task, TaskDecl())
            reconcile(t, payloads, decl.token, decl.stale)
            t.problems = validate(t, d)
            an = analyze_trial(t, decl, rules)
            loaded.append(t)
            c = configs.get(t.config_id)
            poison = sum(1 for f in t.faults if f.type == "poison" and f.delivered)
            rows.append({
                "release": release,
                "config_id": t.config_id,
                "harness": c.harness if c else None,
                "harness_version": c.version if c else None,
                "model": c.model if c else None,
                "route": c.route if c else None,
                "track": t.track,
                "task_id": t.task,
                "profile": t.profile,
                "attempt": t.attempt,
                "reward": t.reward,
                "success": t.success,
                "excluded": t.excluded,
                "infra_failure": t.infra_failure,
                "reported_status": t.status,
                # Overclaim (M7) counts faulted trials with reward below 1 whose STATUS.json says success.
                "overclaim": bool(t.faults) and t.reward is not None and t.reward < 1 and t.status == "success",
                "faults_delivered": sum(1 for f in t.faults if f.delivered),
                "fault_types": dict(sorted(Counter(f.type for f in t.faults if f.delivered).items())),
                "fault_outcomes": dict(sorted(Counter(e.outcome for e in an.events).items())),
                "faults_recovered": sum(1 for e in an.events if e.recovered),
                "poison_delivered": poison,
                "poison_propagated": bool(poison and decl.token and decl.token in t.artifact_text),
                "pathologies": dict(sorted(an.pathologies.items())),
                "eligible_calls": t.eligible_calls,
                "tool_calls": len(t.calls),
                "agent_steps": t.agent_steps,
                "cost_usd": None if t.cost_usd is None else round(t.cost_usd, 6),
                "cost_source": t.cost_source,
                "input_tokens": t.input_tokens,
                "output_tokens": t.output_tokens,
                "wall_seconds": t.wall_seconds,
                "finished_at": t.finished_at,
                "trial_path": t.path,
            })
    mark_superseded(loaded)
    for row, t in zip(rows, loaded):
        row["excluded"] = t.excluded
    return sorted(rows, key=lambda r: (r["track"], r["config_id"], r["task_id"], r["profile"], r["attempt"] or 0, r["trial_path"]))


def jsonl(rows: list[dict[str, Any]]) -> str:
    return "".join(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n" for r in rows)


def render(release: Path, datasets: tuple[Path, ...] | list[Path] = DATASETS, configs_dir: Path = REPO_ROOT / "configs") -> dict[str, str]:
    board = json.loads(next(iter(sorted(release.glob("*/board.json")))).read_text())
    evidence = [REPO_ROOT / e for e in board["meta"]["evidence"]]
    trials = trial_rows(release.name, evidence, datasets, configs_dir)
    tasks = task_rows(datasets, {r["task_id"] for r in trials})
    meta = {"schema": SCHEMA, "release": release.name, "evidence": board["meta"]["evidence"], "tasks": len(tasks), "trials": len(trials)}
    return {"tasks.jsonl": jsonl(tasks), "trials.jsonl": jsonl(trials), "meta.json": dumps(meta)}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m cmca_analysis hf")
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--out", type=Path, help="default: <release>/hf")
    args = parser.parse_args(argv)
    out = args.out or args.release / "hf"
    out.mkdir(parents=True, exist_ok=True)
    for name, text in render(args.release).items():
        (out / name).write_text(text)
        print(out / name)
    return 0
