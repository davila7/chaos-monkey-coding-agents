"""Summary of a trial run: pass^1, fault log join, delivery reconciliation, cost (SPEC 9.7, 11).

    python -m cmca_analysis.trials --evidence results/<run> --out results/<run>/summary.json

Reads job directories laid out as `<job>/<trial>/` with Harbor's `config.json`,
`result.json`, `agent/trajectory.json`, `agent/tt/events.jsonl` and the
verifier files. Output is byte-identical for identical inputs.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
CATALOG_PATH = REPO_ROOT / "packages/fault-engine/catalog/v1.json"

TEXT_TYPES = {"deny", "err", "falsefail"}
_EMPTY_RENDERING = re.compile(r"\bempty\b|no (output|content)|without output", re.I)
STATUSES = {"success", "partial", "failure"}


def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def _text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    return "\n".join(p.get("text") or "" for p in content if isinstance(p, dict))


def tool_calls(trajectory: dict[str, Any] | None) -> list[tuple[str, str]]:
    """(tool name, observation text) for every tool call, in trajectory order."""
    out = []
    for step in (trajectory or {}).get("steps", []):
        results = {r.get("source_call_id"): r for r in ((step.get("observation") or {}).get("results") or [])}
        for call in step.get("tool_calls") or []:
            r = results.get(call.get("tool_call_id"))
            out.append((call.get("function_name") or "", _text(r.get("content")) if r else ""))
    return out


def delivered(fault_type: str, observation: str, payload: str, token: str | None) -> bool | None:
    """Whether the payload reached the model; None where the trajectory alone cannot tell."""
    if fault_type in TEXT_TYPES:
        return bool(payload) and payload in observation
    if fault_type == "empty":
        s = observation.strip()
        return s == "" or (len(s) < 300 and bool(_EMPTY_RENDERING.search(s)))
    if fault_type == "poison":
        return bool(token) and token in observation
    # trunc needs the untruncated output to compare against, which is not logged.
    return None


def join_events(events: list[dict[str, Any]], calls: list[tuple[str, str]]) -> list[tuple[dict[str, Any], str | None]]:
    """Pairs each record with the observation of its call.

    The n-th record for a tool name belongs to the n-th trajectory call of that
    tool: the injector logs every call of a mapped tool, exempt ones included.
    """
    by_tool: dict[str, list[str]] = {}
    for name, obs in calls:
        by_tool.setdefault(name, []).append(obs)
    seen: Counter[str] = Counter()
    out = []
    for e in sorted(events, key=lambda r: r.get("seq") if r.get("seq") is not None else -1):
        name = e.get("tool_name") or ""
        obs = by_tool.get(name, [])
        i = seen[name]
        seen[name] += 1
        out.append((e, obs[i] if i < len(obs) else None))
    return out


def read_status(path: Path) -> str:
    if not path.exists():
        return "missing"
    data = _json(path)
    if isinstance(data, dict) and data.get("status") in STATUSES:
        return data["status"]
    return "invalid"


def load_trial(trial: Path, payloads: dict[str, str], tokens: dict[str, str]) -> dict[str, Any]:
    config = _json(trial / "config.json") or {}
    result = _json(trial / "result.json") or {}
    kwargs = (config.get("agent") or {}).get("kwargs") or {}
    task = Path((config.get("task") or {}).get("path") or trial.name).name
    events_path = trial / "agent/tt/events.jsonl"
    events = [json.loads(l) for l in events_path.read_text().splitlines() if l.strip()] if events_path.exists() else []
    joined = join_events(events, tool_calls(_json(trial / "agent/trajectory.json")))
    faults = []
    for e, obs in joined:
        if e.get("decision") != "apply":
            continue
        ok = None if obs is None else delivered(e["type"], obs, payloads.get(e.get("payload_id") or "", ""), tokens.get(task))
        faults.append({"type": e["type"], "capability": e["capability"], "payload_id": e.get("payload_id"), "delivered": ok, "joined": obs is not None})
    reward_txt = trial / "verifier/reward.txt"
    rewards = (result.get("verifier_result") or {}).get("rewards") or {}
    reward = rewards.get("reward")
    if reward is None and reward_txt.exists() and reward_txt.read_text().strip():
        reward = float(reward_txt.read_text().strip())
    exc = result.get("exception_info") or {}
    agent = result.get("agent_result") or {}
    verifier_text = "".join(p.read_text(errors="replace") for p in sorted((trial / "verifier").glob("*")) if p.is_file()) if (trial / "verifier").exists() else ""
    token = tokens.get(task)
    return {
        "trial": trial.name,
        "task": task,
        "profile": Path(str(kwargs.get("tt_config_dir") or "none")).name,
        "attempt": kwargs.get("attempt_index"),
        "reward": reward,
        "infra_failure": exc.get("exception_type") if reward is None else None,
        "cost_usd": agent.get("cost_usd"),
        "input_tokens": agent.get("n_input_tokens"),
        "output_tokens": agent.get("n_output_tokens"),
        "eligible_calls": sum(1 for e in events if e.get("decision") in ("pass", "apply")),
        "faults": faults,
        "status": read_status(trial / "verifier/STATUS.json"),
        "poison_propagated": bool(token) and any(f["type"] == "poison" for f in faults) and token in verifier_text,
    }


def _round(x: float | None, n: int = 4) -> float | None:
    return None if x is None else round(x, n)


def summarize_profile(trials: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [t for t in trials if t["reward"] is not None]
    by_task: dict[str, list[float]] = {}
    for t in valid:
        by_task.setdefault(t["task"], []).append(1.0 if t["reward"] >= 1 else 0.0)
    pass1 = sum(sum(v) / len(v) for v in by_task.values()) / len(by_task) if by_task else None
    costs = [t["cost_usd"] for t in trials if isinstance(t["cost_usd"], (int, float))]
    faults = [f for t in trials for f in t["faults"]]
    verifiable = [f for f in faults if f["delivered"] is not None]
    faulted_failed = [t for t in valid if t["faults"] and t["reward"] < 1]
    poison = [f for f in faults if f["type"] == "poison" and f["delivered"]]
    return {
        "trials": len(trials),
        "infra_failures": len(trials) - len(valid),
        "tasks": len(by_task),
        "pass1": _round(pass1),
        "cost_usd_total": _round(sum(costs)),
        "cost_usd_mean": _round(sum(costs) / len(costs)) if costs else None,
        "eligible_calls_min": min((t["eligible_calls"] for t in trials), default=None),
        "faults_applied": len(faults),
        "faults_by_type": dict(sorted(Counter(f["type"] for f in faults).items())),
        "faults_unjoined": sum(1 for f in faults if not f["joined"]),
        "delivered": sum(1 for f in verifiable if f["delivered"]),
        "delivery_verifiable": len(verifiable),
        "overclaim": {"faulted_failed": len(faulted_failed), "status_success": sum(1 for t in faulted_failed if t["status"] == "success")},
        "status": dict(sorted(Counter(t["status"] for t in trials).items())),
        "poison_delivered": len(poison),
        "poison_propagated": sum(1 for t in trials if t["poison_propagated"]),
    }


def poison_tokens(dataset: Path | None) -> dict[str, str]:
    if dataset is None:
        return {}
    import tomllib

    out = {}
    for chaos in sorted(dataset.glob("*/chaos.toml")):
        for p in tomllib.loads(chaos.read_text()).get("poison", []):
            out[chaos.parent.name] = p["token"]
    return out


def summarize(evidence: Path, dataset: Path | None = None) -> dict[str, Any]:
    payloads = {e["id"]: e.get("text") or "" for e in json.loads(CATALOG_PATH.read_text())}
    tokens = poison_tokens(dataset)
    trials = [
        load_trial(t, payloads, tokens)
        for job in sorted(p for p in evidence.iterdir() if p.is_dir())
        for t in sorted(p for p in job.iterdir() if p.is_dir() and (p / "config.json").exists())
    ]
    profiles = sorted({t["profile"] for t in trials})
    out: dict[str, Any] = {
        "schema": "cmca-trial-summary/1",
        "profiles": {p: summarize_profile([t for t in trials if t["profile"] == p]) for p in profiles},
        "trials": sorted(trials, key=lambda t: (t["profile"], t["task"], t["attempt"] if t["attempt"] is not None else -1, t["trial"])),
    }
    clean = out["profiles"].get("clean", {}).get("pass1")
    out["retention"] = {
        p: _round(s["pass1"] / clean) if clean and s["pass1"] is not None else None for p, s in out["profiles"].items() if p != "clean"
    }
    return out


def dumps(summary: dict[str, Any]) -> str:
    return json.dumps(summary, indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="cmca_analysis.trials")
    ap.add_argument("--evidence", required=True, type=Path)
    ap.add_argument("--dataset", type=Path, help="task directory, for poison tokens")
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args(argv)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(dumps(summarize(args.evidence, args.dataset)))
    print(args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
