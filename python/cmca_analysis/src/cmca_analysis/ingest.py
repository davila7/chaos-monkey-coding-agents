"""Job directories to trial records (SPEC 9.7 ingest).

A trial directory is `<evidence>/<job>/<trial>/` with Harbor's `config.json`,
`result.json`, `agent/trajectory.json`, the fault log and the verifier files.
The fault log is `agent/tt/events.jsonl` on Track N and the gateway's
`artifacts/var/log/tt/events.jsonl` on Track S. Job names follow
`<config>-<profile>-a<attempt>`.
"""

from __future__ import annotations

import functools
import json
import re
import subprocess
import sys
import tempfile
import tomllib
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
CATALOG_PATH = REPO_ROOT / "packages/fault-engine/catalog/v1.json"
DATASETS = (REPO_ROOT / "datasets/cmca-n", REPO_ROOT / "datasets/cmca-s")

STATUSES = {"success", "partial", "failure"}
ELIGIBLE = ("pass", "apply")
# Harnesses prefix MCP tools with the server name: `mcp__tickets__get_ticket`
# (Claude Code, Pi 1.0.3), `mcp_tickets_get_ticket` (fx), `tickets_get_ticket`
# (OpenCode 1.18.35, V-25). The gateway logs the bare name. OpenCode's prefix
# is only the server name, so it is stripped for the Track S services alone.
MCP_SERVERS = ("tickets", "inventory", "deploy", "docs")
MCP_PREFIX = re.compile(rf"^(?:mcp__?[^_]+__?|(?:{'|'.join(MCP_SERVERS)})_)")
_JOB_NAME = re.compile(r"^(?P<config>.+)-(?P<profile>[a-z0-9]+)-a(?P<attempt>\d+)$")
# Files whose text counts as a final artifact for poison propagation (SPEC 11, M8).
ARTIFACT_GLOBS = ("verifier/*", "artifacts/app/STATUS.json", "artifacts/var/lib/*/state.json")


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def content_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    return "\n".join(p.get("text") or "" for p in content if isinstance(p, dict))


def bare_name(tool: str) -> str:
    return MCP_PREFIX.sub("", tool)


@dataclass
class Call:
    index: int
    step: int  # ordinal of the agent step that issued the call, from 0
    step_id: Any
    tool: str
    args: dict[str, Any]
    observation: str
    capability: str | None = None  # from the joined fault-log record
    decision: str | None = None
    shell_class: str | None = None  # capability class a shell command achieves (SPEC 11.1)
    signature: str | None = None  # class or program of a shell command's lead segment (SPEC 11.1 rule 3)

    @property
    def name(self) -> str:
        return bare_name(self.tool)

    @property
    def command(self) -> str | None:
        cmd = self.args.get("command")
        return cmd if isinstance(cmd, str) else None


@dataclass
class Fault:
    seq: int | None
    type: str
    capability: str
    payload_id: str | None
    persistence: str | None
    call: int | None  # index into Trial.calls, None when the record has no matching call
    delivered: bool | None = None
    attribution_visible: bool | None = None
    step_id: Any = None


@dataclass
class Trial:
    trial: str
    job: str
    path: str
    config_id: str
    track: str
    task: str
    profile: str
    attempt: int | None
    reward: float | None
    infra_failure: str | None
    exception_type: str | None
    cost_usd: float | None
    cost_source: str | None
    input_tokens: int | None
    output_tokens: int | None
    wall_seconds: float | None
    finished_at: str | None
    status: str
    agent_steps: int
    messages: list[str]  # agent message text per agent step
    calls: list[Call]
    events: list[dict[str, Any]]
    faults: list[Fault]
    artifact_text: str
    verifier_text: str
    service_state: dict[str, Any] | None
    poison_eligible: bool | None
    problems: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool | None:
        return None if self.reward is None else self.reward >= 1

    @property
    def eligible_calls(self) -> int:
        return sum(1 for e in self.events if e.get("decision") in ELIGIBLE)

    @property
    def exposure(self) -> dict[str, int]:
        return dict(sorted(Counter(e.get("capability") or "" for e in self.events if e.get("decision") in ELIGIBLE).items()))


@dataclass
class TaskDecl:
    poison: list[dict[str, Any]] = field(default_factory=list)
    non_idempotent: set[str] = field(default_factory=set)
    alternatives: dict[str, set[str]] = field(default_factory=dict)
    # (original, stale) line pairs of every shell poison declaration (D-0037).
    stale: list[tuple[str, str]] = field(default_factory=list)

    @property
    def token(self) -> str | None:
        return self.poison[0]["token"] if self.poison else None


@functools.cache
def _generated(build: Path) -> Path:
    """Output of a task's `environment/gen/build.py`, which some Track N images run to build /app."""
    out = Path(tempfile.mkdtemp(prefix="tt-gen-"))
    subprocess.run([sys.executable, str(build), str(out / "app")], check=True, capture_output=True)
    return out / "app"


def source_text(task_dir: Path, rel: str) -> str:
    """A file as it is under /app in the task image: copied from environment/, or generated."""
    direct = task_dir / "environment" / rel
    if direct.exists():
        return direct.read_text()
    build = task_dir / "environment/gen/build.py"
    if build.exists():
        return (_generated(build.resolve()) / rel).read_text()
    raise FileNotFoundError(direct)


def stale_lines(original: str, variant: str) -> list[tuple[str, str]]:
    """The lines shell poison replaces, as fault-engine `staleLines` computes them."""
    a, b = original.split("\n"), variant.split("\n")
    if len(a) != len(b):
        return []
    return [(x, y) for x, y in zip(a, b) if x != y and x != ""]


def shell_stale(task_dir: Path, poison: list[dict[str, Any]]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for p in poison:
        source = p.get("source")
        if p.get("tool") == "shell" and isinstance(source, str):
            variant = (task_dir / p["variant"]).read_text()
            pairs += stale_lines(source_text(task_dir, source.removeprefix("/app/")), variant)
    return pairs


def task_decls(datasets: tuple[Path, ...] | list[Path]) -> dict[str, TaskDecl]:
    out: dict[str, TaskDecl] = {}
    for dataset in datasets:
        for chaos in sorted(Path(dataset).glob("*/chaos.toml")):
            data = tomllib.loads(chaos.read_text())
            poison = data.get("poison", [])
            out[chaos.parent.name] = TaskDecl(
                poison=poison,
                non_idempotent={d["tool"] for d in data.get("non_idempotent", [])},
                alternatives={a["tool"]: set(a.get("via", [])) for a in data.get("alternatives", [])},
                stale=shell_stale(chaos.parent, poison),
            )
    return out


def payload_texts() -> dict[str, str]:
    return {e["id"]: e.get("text") or "" for e in json.loads(CATALOG_PATH.read_text())}


def trajectory_steps(trajectory: dict[str, Any] | None) -> tuple[list[str], list[Call]]:
    """Agent message text per agent step and every tool call in trajectory order."""
    messages: list[str] = []
    calls: list[Call] = []
    for step in (trajectory or {}).get("steps", []):
        if step.get("source") != "agent":
            continue
        ordinal = len(messages)
        messages.append(content_text(step.get("message")))
        results = {r.get("source_call_id"): r for r in ((step.get("observation") or {}).get("results") or [])}
        for call in step.get("tool_calls") or []:
            r = results.get(call.get("tool_call_id"))
            args = call.get("arguments")
            calls.append(
                Call(
                    index=len(calls),
                    step=ordinal,
                    step_id=step.get("step_id"),
                    tool=call.get("function_name") or "",
                    args=args if isinstance(args, dict) else {},
                    observation=content_text(r.get("content")) if r else "",
                )
            )
    return messages, calls


def join(events: list[dict[str, Any]], calls: list[Call]) -> list[tuple[dict[str, Any], Call | None]]:
    """Pairs each fault-log record with its trajectory call.

    The n-th record for a tool name belongs to the n-th trajectory call of that
    tool: the injector logs every call of a mapped tool, exempt ones included.
    """
    by_tool: dict[str, list[Call]] = {}
    for c in calls:
        by_tool.setdefault(c.name, []).append(c)
    seen: Counter[str] = Counter()
    out = []
    for e in sorted(events, key=lambda r: r.get("seq") if r.get("seq") is not None else -1):
        name = e.get("tool_name") or ""
        same = by_tool.get(name, [])
        i = seen[name]
        seen[name] += 1
        out.append((e, same[i] if i < len(same) else None))
    return out


def parse_job(job: str) -> tuple[str, str | None, int | None]:
    m = _JOB_NAME.match(job)
    if not m:
        return job, None, None
    return m.group("config"), m.group("profile"), int(m.group("attempt"))


def read_status(path: Path) -> str:
    if not path.exists():
        return "missing"
    data = read_json(path)
    if isinstance(data, dict) and data.get("status") in STATUSES:
        return data["status"]
    return "invalid"


def _seconds(span: dict[str, Any] | None) -> float | None:
    if not span or not span.get("started_at") or not span.get("finished_at"):
        return None
    start = datetime.fromisoformat(span["started_at"].replace("Z", "+00:00"))
    end = datetime.fromisoformat(span["finished_at"].replace("Z", "+00:00"))
    return round((end - start).total_seconds(), 3)


def _texts(trial: Path, globs: tuple[str, ...]) -> str:
    files = sorted({p for g in globs for p in trial.glob(g) if p.is_file()})
    return "".join(p.read_text(errors="replace") for p in files)


def events_path(trial: Path) -> Path:
    native = trial / "agent/tt/events.jsonl"
    return native if native.exists() else trial / "artifacts/var/log/tt/events.jsonl"


def _track(config: dict[str, Any], events: list[dict[str, Any]], task: str) -> str:
    source = (config.get("task") or {}).get("source") or ""
    if source.endswith("-s"):
        return "s"
    if source.endswith("-n"):
        return "n"
    layers = {e.get("layer") for e in events}
    if "service" in layers:
        return "s"
    return "s" if task.startswith("s-") else "n"


def load_trial(
    trial: Path,
    root: Path,
    decls: dict[str, TaskDecl],
    settled: dict[str, float] | None = None,
) -> Trial:
    """One trial record. `root` is the evidence directory; `settled` maps `<job>/<trial>` to a settled cost."""
    config = read_json(trial / "config.json") or {}
    result = read_json(trial / "result.json") or {}
    kwargs = (config.get("agent") or {}).get("kwargs") or {}
    task = Path((config.get("task") or {}).get("path") or trial.name).name
    job = trial.parent.name
    config_id, job_profile, job_attempt = parse_job(job)
    profile = Path(str(kwargs["tt_config_dir"])).name if kwargs.get("tt_config_dir") else (job_profile or "none")
    attempt = kwargs.get("attempt_index", job_attempt)

    ev_path = events_path(trial)
    events = [json.loads(l) for l in ev_path.read_text().splitlines() if l.strip()] if ev_path.exists() else []
    messages, calls = trajectory_steps(read_json(trial / "agent/trajectory.json"))
    pairs = join(events, calls)
    for e, c in pairs:
        if c is not None:
            c.capability = e.get("capability")
            c.decision = e.get("decision")
    decl = decls.get(task, TaskDecl())
    faults = [
        Fault(
            seq=e.get("seq"),
            type=e["type"],
            capability=e.get("capability") or "",
            payload_id=e.get("payload_id"),
            persistence=e.get("persistence"),
            call=c.index if c else None,
            step_id=c.step_id if c else None,
        )
        for e, c in pairs
        if e.get("decision") == "apply"
    ]

    rewards = (result.get("verifier_result") or {}).get("rewards") or {}
    reward = rewards.get("reward")
    reward_txt = trial / "verifier/reward.txt"
    if reward is None and reward_txt.exists() and reward_txt.read_text().strip():
        reward = float(reward_txt.read_text().strip())
    exc = result.get("exception_info") or {}
    agent = result.get("agent_result") or {}
    key = f"{job}/{trial.name}"
    cost, cost_source = agent.get("cost_usd"), "result.json"
    if settled and key in settled:
        cost, cost_source = settled[key], "settled-usage.json"
    elif cost is None:
        cost_source = None

    try:
        path = str(trial.resolve().relative_to(REPO_ROOT))
    except ValueError:
        path = str(trial.relative_to(root.parent))
    return Trial(
        trial=trial.name,
        job=job,
        path=path,
        config_id=config_id,
        track=_track(config, events, task),
        task=task,
        profile=profile,
        attempt=attempt,
        reward=reward,
        infra_failure=exc.get("exception_type") if reward is None else None,
        exception_type=exc.get("exception_type"),
        cost_usd=cost,
        cost_source=cost_source,
        input_tokens=agent.get("n_input_tokens"),
        output_tokens=agent.get("n_output_tokens"),
        wall_seconds=_seconds(result.get("agent_execution")),
        finished_at=result.get("finished_at"),
        status=read_status(trial / "verifier/STATUS.json"),
        agent_steps=len(messages),
        messages=messages,
        calls=calls,
        events=events,
        faults=faults,
        artifact_text=_texts(trial, ARTIFACT_GLOBS),
        verifier_text=_texts(trial, ("verifier/*",)),
        service_state=next((read_json(p) for p in sorted(trial.glob("artifacts/var/lib/*/state.json"))), None),
        poison_eligible=poison_eligible(pairs, decl.poison) if decl.poison else None,
    )


def poison_eligible(pairs: list[tuple[dict[str, Any], Call | None]], decls: list[dict[str, Any]]) -> bool:
    """Whether any eligible call matched a poison declaration, so a poison fault could have been drawn."""
    for e, c in pairs:
        if c is None or e.get("decision") not in ELIGIBLE:
            continue
        for d in decls:
            if e.get("capability") == d.get("tool") and all(c.args.get(k) == v for k, v in (d.get("match") or {}).items()):
                return True
    return False


def settled_costs(evidence: Path) -> dict[str, float]:
    """Settled per-trial cost where the gateway's records arrived after the trial (D-0030)."""
    data = read_json(evidence / "settled-usage.json")
    if not isinstance(data, dict):
        return {}
    return {k: v["settled_total_cost"] for k, v in data.items() if isinstance(v, dict) and isinstance(v.get("settled_total_cost"), (int, float))}


def trial_dirs(evidence: Path) -> list[Path]:
    return [
        t
        for job in sorted(p for p in evidence.iterdir() if p.is_dir())
        for t in sorted(p for p in job.iterdir() if p.is_dir() and (p / "config.json").exists())
    ]


def load_evidence(evidence: Path, decls: dict[str, TaskDecl]) -> list[Trial]:
    settled = settled_costs(evidence)
    return [load_trial(t, evidence, decls, settled) for t in trial_dirs(evidence)]
