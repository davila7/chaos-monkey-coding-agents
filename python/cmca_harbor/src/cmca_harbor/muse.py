"""Muse Code with Meta's own model on the native axis (D-0047).

Harbor's `muse-code` agent installs the latest release; this one installs a
binary pinned by version and sha256 from Meta's release manifest, with
auto-update off. Muse calls Meta's API directly (`--provider meta`, no base
URL) in Standard mode (`--contributor-mode off`), so task content is not
training data.

Track N faults go through one hook command for PreToolUse, PostToolUse and
PostToolUseFailure (packages/injector-muse), set in the user settings file
Harbor writes, so nothing is added to the task workspace. Muse runs hooks with
a cleared environment (V-29), so the command carries the injector's paths.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import Field

from harbor.agents.installed.muse_code import MuseCode, MuseCodeOptions

from cmca_harbor.common import REMOTE_CONFIG, REMOTE_LOG, REMOTE_ROOT, REMOTE_STATE, TtAgentMixin, TtOptions

DOWNLOAD = "https://lookaside.facebook.com/lookaside/muse/download/?channel=muse&version={version}&file=muse-{arch}-linux"
# sha256 of the linux binaries from Meta's release manifest
# (docs/verification/V-29/2026-10-31-manifest.json).
BINARIES = {
    "1.4.14-R7309.1": {
        "x86": "0809aac7cb58d18f5022b6d05e02aa1974683c0ec430e5f04d25b60ed17de2da",
        "aarch64": "3dc39b8fa26f9963cc2038f2966c0932ed5a39f0f9efb39cc0266a261cbbcf76",
    },
}

# USD per million tokens, Meta list prices, Standard mode
# (https://dev.meta.ai/docs/pricing-rate-limits, read 2026-10-31; D-0047).
# No cache write price is listed. Output includes reasoning tokens (V-29).
PRICES = {
    "muse-spark-1.3": {"input": 1.25, "cached_input": 0.15, "output": 4.25},
}


def usage_cost(model: str | None, prompt: int | None, cached: int | None, output: int | None) -> float | None:
    price = PRICES.get(model or "")
    if price is None or prompt is None or output is None:
        return None
    cached = cached or 0
    return ((prompt - cached) * price["input"] + cached * price["cached_input"] + output * price["output"]) / 1e6


def redact_builtin_prompts(trajectory: dict[str, Any]) -> int:
    """Replaces the text of `system` steps, Muse Code's built-in prompts, with
    their sha256 and length, in the trajectory and its subagent trajectories.

    The prompts are part of Meta's Downloadable Materials, which the terms do
    not let us redistribute (V-30, 10.1(xiv)); trial evidence is published.
    """
    n = 0
    for step in trajectory.get("steps") or []:
        message = step.get("message")
        if step.get("source") == "system" and isinstance(message, str) and not message.startswith("[redacted"):
            digest = hashlib.sha256(message.encode()).hexdigest()
            step["message"] = f"[redacted: Muse Code built-in prompt, sha256 {digest}, {len(message)} characters (V-30)]"
            n += 1
    for child in trajectory.get("subagent_trajectories") or []:
        n += redact_builtin_prompts(child)
    return n


def redact_file(path: Path) -> int:
    trajectory = json.loads(path.read_text())
    n = redact_builtin_prompts(trajectory)
    if n:
        path.write_text(json.dumps(trajectory, indent=2) + "\n")
    return n


class ChaosMuseOptions(MuseCodeOptions, TtOptions):
    # Muse starts reminder agents that make their own model calls; their cost
    # is only partly in the session logs (V-29).
    disable_reminders: bool = Field(default=False)


class ChaosMuse(TtAgentMixin, MuseCode):
    options_model = ChaosMuseOptions
    HARNESS_DIR = "muse"
    # Harbor 0.24.0's agent writes MCP servers into Muse's settings but does
    # not declare it, so Harbor refuses Track S tasks without this.
    capabilities = MuseCode.capabilities.model_copy(update={"mcp_servers": True})

    @staticmethod
    def name() -> str:
        return "chaos-muse"

    def _pin(self) -> tuple[str, dict[str, str]]:
        version = self._version or ""
        sums = BINARIES.get(version)
        if sums is None:
            raise ValueError(f"muse {version!r}: no pinned binary checksum; add it to cmca_harbor.muse.BINARIES")
        return version, sums

    def install_script(self) -> str:
        version, sums = self._pin()
        cases = " ".join(f"{arch}) sum={sha};;" for arch, sha in sums.items())
        url = DOWNLOAD.format(version=version, arch="$a")
        return (
            "set -euo pipefail; "
            'case "$(uname -m)" in x86_64|amd64) a=x86;; aarch64|arm64) a=aarch64;; *) a=$(uname -m);; esac; '
            f'case "$a" in {cases} *) echo "unsupported arch $a" >&2; exit 1;; esac; '
            f't=$(mktemp -d); curl -fsSL "{url}" -o $t/muse; '
            'echo "$sum  $t/muse" | sha256sum -c -; '
            'mkdir -p "$HOME/.local/bin"; install -m 755 $t/muse "$HOME/.local/bin/muse"; rm -rf $t; '
            f"{self._PATH_EXPORT}; MUSE_NO_AUTO_UPDATE=1 muse --version"
        )

    async def install(self, environment) -> None:
        self._pin()
        # Node runs the injector, as for the fxh agent; installed in every
        # condition so clean and faulted trials share one installation.
        await self.ensure_system_dependencies(environment, ("curl", "bash", "ca_certificates", "coreutils", "git", "nodejs"))
        await self._ca_env_and_system_bundle(environment)
        await self.exec_as_agent(environment, command=self.install_script())

    def get_version_command(self) -> str | None:
        return f"{self._PATH_EXPORT}; MUSE_NO_AUTO_UPDATE=1 muse --version"

    def parse_version(self, stdout: str) -> str:
        # `Muse Code 1.4.14 (1.4.14-R7309.1)`: the build id is the pin.
        start, end = stdout.find("("), stdout.find(")")
        return stdout[start + 1 : end] if 0 <= start < end else super().parse_version(stdout)

    def _hook_command(self) -> str:
        env = f"TT_CONFIG={REMOTE_CONFIG} TT_STATE={REMOTE_STATE} TT_LOG={REMOTE_LOG} TT_DECIDE={REMOTE_ROOT}/bin/tt-decide.cjs"
        return f"env {env} node {REMOTE_ROOT}/{self.HARNESS_DIR}/index.cjs"

    def _build_effective_config(self) -> dict[str, Any]:
        config = super()._build_effective_config()
        if self._tt_active():
            # `*` is the matcher V-29 tested; the injector passes tools it does not map.
            group = [{"matcher": "*", "hooks": [{"type": "command", "command": self._hook_command(), "timeout": 30}]}]
            config["hooks"] = {"PreToolUse": group, "PostToolUse": group, "PostToolUseFailure": group}
        return config

    def build_cli_flags(self) -> str:
        flags = [super().build_cli_flags(), "--provider meta", "--contributor-mode off"]
        if self.options.disable_reminders:
            flags.append("--disable-reminders")
        return " ".join(f for f in flags if f)

    async def run(self, instruction, environment, context) -> None:
        if self.options.base_url or self.model_connection.configured_base_url:
            raise ValueError("chaos-muse calls Meta's API only; a base URL is not allowed (D-0047, V-30)")
        env = await self._tt_prepare(environment)
        with environment.scoped_exec_env(env):
            await super().run(instruction, environment, context)

    def populate_context_post_run(self, context) -> None:
        super().populate_context_post_run(context)
        trajectory = self.logs_dir / "trajectory.json"
        if trajectory.exists():
            redact_file(trajectory)
        # Harbor sums the tokens of the root session and the child sessions
        # that left a log; Muse reports no price, so cost comes from the list
        # prices. Reminder calls without a log are not in this figure (V-29).
        context.cost_usd = usage_cost(self._model_slug(), context.n_input_tokens, context.n_cache_tokens, context.n_output_tokens)
        metadata = dict(context.metadata or {})
        metadata["muse"] = {"run_usage": self._run_usage(), "reminder_tasks": self._reminder_tasks()}
        context.metadata = metadata
        self._tt_metadata(context)

    def _events(self) -> list[dict[str, Any]]:
        path = self.logs_dir / self._OUTPUT_FILENAME
        if not path.exists():
            return []
        out = []
        for line in path.read_text().splitlines():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
        return out

    def _run_usage(self) -> list[dict[str, Any]]:
        """`run.usage` from `exec --json`: the main agent's calls only (`children_included: false`)."""
        return [e["payload"] for e in self._events() if e.get("payload_type") == "run.usage"]

    def _reminder_tasks(self) -> int:
        return sum(
            1
            for e in self._events()
            if e.get("payload_type") == "task.lifecycle.proposed"
            and str((e.get("payload", {}).get("event") or {}).get("task_kind", "")).startswith("reminder.")
        )

