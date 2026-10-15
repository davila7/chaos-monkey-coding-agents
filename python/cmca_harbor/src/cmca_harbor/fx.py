"""fx on Track S: Harbor's `fx` agent plus session collection and an ATIF trajectory.

fx has no interception point for its built-in tools (D-0027), so nothing is
injected here; the gateway in the task's compose file applies the faults. This
agent pins the release archive by checksum, copies the fx session journal into
`/logs/agent` after the run, and converts it to ATIF (V-09).
"""

import json
import shlex
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from harbor.agents.installed.fx import Fx, FxOptions
from harbor.models.trajectories import Agent, FinalMetrics, Observation, ObservationResult, Step, ToolCall, Trajectory

from cmca_harbor.common import REMOTE_CA, REMOTE_ROOT, TtOptions

RELEASES = "https://releases.fx.sh"
# sha256 of fx-linux-<arch>.tar.gz; releases.fx.sh publishes no checksum file.
ARCHIVES = {
    "0.0.13": {
        "x86_64": "53a3b30ce1541048f8fa4b42b7bc68161466bb2e3708db104449a58af3807430",
        "aarch64": "78f6a8171193a1d2033f93d1b5a2940ea4a62147daf60a37ae670a9bf85f12e9",
    },
}
SESSION_DIR = "fx-session"
GENERATION_URL = "https://ai-gateway.vercel.sh/v1/generation?id={}"


class ChaosFxOptions(FxOptions, TtOptions):
    pass


def _text(result: dict[str, Any], session: Path) -> str:
    ref = result.get("artifact_ref")
    if ref and (session / "tool-results" / ref).exists():
        return (session / "tool-results" / ref).read_text(errors="replace")
    return result.get("preview") or ""


def settle_usage(snapshot: dict[str, Any], fetch: Callable[[str], dict[str, Any] | None]) -> dict[str, Any] | None:
    """Cost and cache reads with fx's unsettled generations resolved; None when a lookup fails.

    fx copies `usage-v2.json` before its billing settles: requests still in
    `snapshot.pending` are missing from `total_cost` (V-08).
    """
    cost = float(snapshot.get("total_cost") or 0)
    cached = int(snapshot.get("cache_read_tokens") or 0)
    for pending in snapshot.get("pending") or []:
        g = fetch(pending["id"])
        if g is None:
            return None
        cost += float(g.get("total_cost") or 0)
        cached += int(g.get("native_tokens_cached") or 0)
    return {"total_cost": cost, "cache_read_tokens": cached}


def gateway_generation(api_key: str, attempts: int = 12, sleep: Callable[[float], None] = time.sleep) -> Callable[[str], dict[str, Any] | None]:
    # A generation record can take minutes to appear (404 until then, V-08); the
    # default waits about three minutes per missing record.
    def fetch(generation_id: str) -> dict[str, Any] | None:
        req = urllib.request.Request(GENERATION_URL.format(generation_id), headers={"Authorization": f"Bearer {api_key}"})
        for i in range(attempts):
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    return json.load(r).get("data")
            except (OSError, ValueError):
                if i < attempts - 1:
                    sleep(min(5 * (i + 1), 20))
        return None

    return fetch


def session_to_atif(
    session: Path, *, version: str, model: str | None, usage: dict[str, Any] | None = None, settled: dict[str, Any] | None = None
) -> Trajectory:
    """ATIF from an fx `sessions/<id>/` directory (`events.jsonl` schema_version 3).

    `usage` is the `usage` object of fx's `--json` output (token totals over every
    request); `settled` comes from `settle_usage`. Without `settled`, a cost is
    reported only when the snapshot has nothing pending.
    """
    events = [json.loads(line)["event"] for line in (session / "events.jsonl").read_text().splitlines() if line.strip()]
    steps: list[Step] = []
    pending: dict[str, Step] = {}

    def add(**kw) -> Step:
        s = Step(step_id=len(steps) + 1, **kw)
        steps.append(s)
        return s

    current: Step | None = None
    for ev in events:
        (kind, body), = ev.items()
        if kind == "user":
            current = None
            add(source="user", message=body.get("text", ""))
        elif kind == "assistant":
            current = add(source="agent", model_name=model, message=body.get("text", ""))
        elif kind == "tool_call":
            if current is None:
                current = add(source="agent", model_name=model, message="")
            try:
                args = json.loads(body.get("arguments_json") or "{}")
            except ValueError:
                args = {"_raw": body.get("arguments_json")}
            call = ToolCall(tool_call_id=body["call_id"], function_name=body["tool_name"], arguments=args if isinstance(args, dict) else {"_value": args})
            current.tool_calls = [*(current.tool_calls or []), call]
            pending[body["call_id"]] = current
        elif kind == "tool_result":
            owner = pending.get(body["call_id"])
            if owner is None:
                continue
            res = ObservationResult(source_call_id=body["call_id"], content=_text(body, session), extra={"status": body.get("status")})
            owner.observation = Observation(results=[*(owner.observation.results if owner.observation else []), res])
    snapshot: dict[str, Any] = {}
    usage_file = session / "usage-v2.json"
    if usage_file.exists():
        snapshot = json.loads(usage_file.read_text()).get("snapshot", {})
    if settled is None and not snapshot.get("pending"):
        settled = {"total_cost": snapshot.get("total_cost"), "cache_read_tokens": snapshot.get("cache_read_tokens")}
    usage = usage or {}
    final = FinalMetrics(
        total_prompt_tokens=usage.get("input_tokens", snapshot.get("input_tokens")),
        total_completion_tokens=usage.get("output_tokens", snapshot.get("output_tokens")),
        total_cached_tokens=(settled or {}).get("cache_read_tokens"),
        total_cost_usd=(settled or {}).get("total_cost"),
        total_steps=len(steps),
    )
    return Trajectory(
        schema_version="ATIF-v1.5",
        session_id=session.name,
        agent=Agent(name="fx", version=version, model_name=model),
        steps=steps,
        final_metrics=final,
    )


class ChaosFx(Fx):
    options_model = ChaosFxOptions

    @staticmethod
    def name() -> str:
        return "chaos-fx"

    def resolve_env_vars(self) -> dict[str, str]:
        # AI Gateway retries a failed model request on every provider of the model,
        # even a non-retryable 400 (V-08). Pinning the provider named in the model id
        # makes fx send `providerOptions.gateway.only`, so one request is one attempt.
        env = super().resolve_env_vars()
        provider = (self.model_name or "").removeprefix("vercel_ai_gateway/").partition("/")[0]
        if provider and "FX_PROVIDER_ORDER" not in env:
            env["FX_PROVIDER_ORDER"] = provider
            env["FX_PROVIDER_STRICT"] = "1"
        return env

    async def _trust_extra_ca(self, environment) -> None:
        if not self.options.extra_ca_cert:
            return
        await self.exec_as_root(environment, command=f"mkdir -p {REMOTE_ROOT}")
        await environment.upload_file(Path(self.options.extra_ca_cert), REMOTE_CA)
        await self.exec_as_root(environment, command=f"cat {REMOTE_CA} >> /etc/ssl/certs/ca-certificates.crt")

    async def install(self, environment) -> None:
        version = (self._version or "").removeprefix("v")
        sums = ARCHIVES.get(version)
        if sums is None:
            raise ValueError(f"fx {version!r}: no pinned archive checksum; add it to cmca_harbor.fx.ARCHIVES")
        await self.ensure_system_dependencies(environment, ("curl", "bash", "ca_certificates", "tar", "coreutils", "tmux"))
        await self._trust_extra_ca(environment)
        cases = " ".join(f"{arch}) sum={sha};;" for arch, sha in sums.items())
        script = (
            "set -euo pipefail; "
            f'case "$(uname -m)" in amd64) a=x86_64;; arm64) a=aarch64;; *) a=$(uname -m);; esac; '
            f'case "$a" in {cases} *) echo "unsupported arch $a" >&2; exit 1;; esac; '
            f"t=$(mktemp -d); curl -fsSL {RELEASES}/v{version}/fx-linux-$a.tar.gz -o $t/fx.tgz; "
            'echo "$sum  $t/fx.tgz" | sha256sum -c -; '
            'tar -xzf $t/fx.tgz -C $t; mkdir -p "$HOME/.local/bin"; mv $t/fx "$HOME/.local/bin/fx"; '
            f"{self._PATH_EXPORT}; fx --version"
        )
        await self.exec_as_agent(environment, command=script)
        await self._configure(environment)

    async def _configure(self, environment) -> None:
        """The parent install after its download: settings, skills, MCP servers."""
        if self.options.reasoning_effort is not None:
            await self._upload_config_text(
                environment, content=json.dumps({"effort": self.options.reasoning_effort}), remote_path="/tmp/fx-settings.json", filename="settings.json"
            )
            await self.exec_as_agent(environment, command='mkdir -p "$HOME/.fx" && mv /tmp/fx-settings.json "$HOME/.fx/settings.json"')
        skills = self._build_register_skills_command()
        if skills:
            await self.exec_as_agent(environment, command=skills)
        if self.mcp_servers:
            await self._upload_config_text(environment, content=self._build_mcp_config(), remote_path="/tmp/fx-mcp.json", filename="mcp.json")
            await self.exec_as_agent(environment, command='mkdir -p "$HOME/.fx" && mv /tmp/fx-mcp.json "$HOME/.fx/mcp.json" && chmod 600 "$HOME/.fx/mcp.json"')

    async def run(self, instruction, environment, context) -> None:
        try:
            await super().run(instruction, environment, context)
        finally:
            out = f"/logs/agent/{SESSION_DIR}"
            # The session id is in fx.json; when the run died before writing it, take the newest session.
            pick = (
                "id=$(python3 -c 'import json,sys; print(json.load(open(\"/logs/agent/fx.json\")).get(\"session_id\",\"\"))' 2>/dev/null || true); "
                'd="$HOME/.fx/sessions/$id"; [ -n "$id" ] && [ -d "$d" ] || d=$(ls -dt "$HOME"/.fx/sessions/*/ 2>/dev/null | head -1); '
                f'if [ -n "$d" ]; then mkdir -p {shlex.quote(out)} && cp -r "$d"/. {shlex.quote(out)}/; fi'
            )
            await self.exec_as_agent(environment, command=pick)

    def populate_context_post_run(self, context) -> None:
        session = self.logs_dir / SESSION_DIR
        summary_path = self.logs_dir / self._OUTPUT_FILENAME
        summary: dict[str, Any] = {}
        if summary_path.exists():
            try:
                summary = json.loads(summary_path.read_text())
            except ValueError:
                summary = {}
        if not (session / "events.jsonl").exists():
            return
        settled = None
        usage_file = session / "usage-v2.json"
        if usage_file.exists() and self.model_connection.api_key:
            snapshot = json.loads(usage_file.read_text()).get("snapshot", {})
            settled = settle_usage(snapshot, gateway_generation(self.model_connection.api_key))
        traj = session_to_atif(
            session, version=self._version or "", model=summary.get("model") or self.model_name, usage=summary.get("usage"), settled=settled
        )
        (self.logs_dir / "trajectory.json").write_text(json.dumps(traj.to_json_dict(), indent=2))
        fm = traj.final_metrics
        if fm is not None:
            context.n_input_tokens = fm.total_prompt_tokens
            context.n_output_tokens = fm.total_completion_tokens
            context.n_cache_tokens = fm.total_cached_tokens
            context.cost_usd = fm.total_cost_usd
