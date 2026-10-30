"""Codex CLI on Claude through a loopback Responses API bridge (D-0044).

Codex 0.163.0 calls custom providers only through the Responses API, which
the Anthropic API does not offer. `packages/responses-bridge` runs inside the
agent container on 127.0.0.1, takes Codex's requests and calls the Messages
API with the trial's key (V-28). Codex knows no metadata for Claude models, so
the model comes from a catalog entry built from Codex's own (V-03): the tool
settings of its `gpt-5.5` entry, which declare `apply_patch` as a tool, and
the generic prompt Codex sends to a model it does not know.

Track N faults go through one command for PreToolUse and PostToolUse
(packages/injector-codex), set inline in config.toml.
"""

import json
import os
import shlex
from pathlib import Path
from typing import Any

from harbor.agents.installed.codex import Codex, CodexOptions

from cmca_harbor.common import REMOTE_ROOT, REPO_ROOT, TtAgentMixin, TtOptions

BRIDGE_BUILD = REPO_ROOT / "packages/responses-bridge/dist/tt/bridge"
CATALOG = REPO_ROOT / "configs/codex-claude.catalog.json"
# Agent-visible, so neutral (SPEC 7.2).
REMOTE_BRIDGE = f"{REMOTE_ROOT}/bridge"
REMOTE_CATALOG = f"{REMOTE_ROOT}/models.json"
REMOTE_USAGE = "/logs/agent/bridge/usage.jsonl"
BRIDGE_PORT = 18080
PROVIDER = "anthropic-bridge"
# Calls the injector maps to a capability class; MCP tools belong to the Track S proxy.
TOOLS = "^(Bash|apply_patch)$"

# USD per million tokens, Anthropic list prices for the pinned model
# (https://platform.claude.com/docs/en/about-claude/pricing, read
# 2026-10-30). Cache writes use the 5-minute TTL that automatic caching sets.
PRICES = {
    "claude-sonnet-5-5": {"input": 2.00, "output": 10.00, "cache_read": 0.10, "cache_write": 2.50},
}


def usage_cost(records: list[dict[str, Any]]) -> tuple[float | None, dict[str, int]]:
    """Cost and token totals of the bridge's usage records. Cost is None when a
    record names a model without a price."""
    totals = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
    cost = 0.0
    for r in records:
        u = r.get("usage") or {}
        n = {
            "input": u.get("input_tokens") or 0,
            "output": u.get("output_tokens") or 0,
            "cache_read": u.get("cache_read_input_tokens") or 0,
            "cache_write": u.get("cache_creation_input_tokens") or 0,
        }
        for k, v in n.items():
            totals[k] += v
        price = PRICES.get(r.get("model", ""))
        if price is None:
            return None, totals
        cost += sum(n[k] * price[k] for k in n) / 1e6
    return cost, totals


class ChaosCodexOptions(CodexOptions, TtOptions):
    pass


class ChaosCodex(TtAgentMixin, Codex):
    options_model = ChaosCodexOptions
    HARNESS_DIR = "codex"

    @staticmethod
    def name() -> str:
        return "chaos-codex"

    def _codex_config(self) -> dict[str, Any]:
        config: dict[str, Any] = {
            "model_provider": PROVIDER,
            "model_catalog_json": REMOTE_CATALOG,
            # Hosted tools do not run against the Messages API, and Codex's
            # sub-agents arrive as a tool namespace the bridge does not map.
            "web_search": "disabled",
            "model_providers": {
                PROVIDER: {
                    "name": PROVIDER,
                    "base_url": f"http://127.0.0.1:{BRIDGE_PORT}/v1",
                    "wire_api": "responses",
                    "supports_websockets": False,
                    # The bridge answers once the whole model response is in; keep-alive
                    # events arrive every 10 s, and this bounds the wait if they stop.
                    "stream_idle_timeout_ms": 1_800_000,
                },
            },
            "features": {"multi_agent": False},
        }
        if self._tt_active():
            command = f"node {REMOTE_ROOT}/{self.HARNESS_DIR}/index.cjs"
            group = [{"matcher": TOOLS, "hooks": [{"type": "command", "command": command, "timeout": 30}]}]
            config["features"]["hooks"] = True
            config["hooks"] = {"PreToolUse": group, "PostToolUse": group}
        return config

    def _build_effective_config(self, openai_base_url: str | None = None) -> dict[str, Any]:
        config = super()._build_effective_config(openai_base_url)
        for key, value in self._codex_config().items():
            if isinstance(value, dict) and isinstance(config.get(key), dict):
                config[key] = {**config[key], **value}
            else:
                config[key] = value
        return config

    def build_cli_flags(self) -> str:
        flags = super().build_cli_flags()
        if self._tt_active() and "--dangerously-bypass-hook-trust" not in flags:
            flags = f"{flags} --dangerously-bypass-hook-trust".strip()
        return flags

    async def install(self, environment) -> None:
        if not self._version or self._version == "latest":
            raise ValueError("ChaosCodex installs a pinned Codex version; pass --ak version=<x.y.z>")
        await self.ensure_system_dependencies(environment, ("curl", "bash", "ca_certificates", "nodejs", "npm", "ripgrep"))
        ca = await self._ca_env_and_system_bundle(environment)
        with environment.scoped_exec_env(ca):
            await super().install(environment)

    def _model_env(self) -> dict[str, str]:
        """What the bridge needs to reach the Messages API. The base URL is
        never passed: the host's ANTHROPIC_BASE_URL can point elsewhere (V-10)."""
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise ValueError("ANTHROPIC_API_KEY is required for the bridge")
        return {"ANTHROPIC_API_KEY": key}

    async def _start_bridge(self, environment, env: dict[str, str]) -> None:
        if not (BRIDGE_BUILD / "index.cjs").exists():
            raise FileNotFoundError(f"{BRIDGE_BUILD / 'index.cjs'} missing; run `pnpm build`")
        model_env = self._model_env()
        await self.exec_as_root(environment, command=f"mkdir -p {REMOTE_ROOT} {Path(REMOTE_USAGE).parent}")
        await environment.upload_dir(BRIDGE_BUILD, REMOTE_BRIDGE)
        await environment.upload_file(CATALOG, REMOTE_CATALOG)
        owner = environment.default_user
        if owner is not None:
            await self.exec_as_root(environment, command=f"chown -R {shlex.quote(str(owner))} {Path(REMOTE_USAGE).parent}")
        await self.exec_as_root(environment, command=f"chmod -R a+rX {REMOTE_ROOT}")
        bridge_env = {
            **env,
            **model_env,
            "BRIDGE_PORT": str(BRIDGE_PORT),
            "BRIDGE_USAGE_LOG": REMOTE_USAGE,
        }
        log = f"{Path(REMOTE_USAGE).parent}/server.log"
        await self.exec_as_agent(
            environment,
            command=(
                "if [ -s ~/.nvm/nvm.sh ]; then . ~/.nvm/nvm.sh; fi; "
                f"nohup node {REMOTE_BRIDGE}/index.cjs > {log} 2>&1 < /dev/null & "
                f'for i in $(seq 1 50); do grep -q listening {log} && exit 0; sleep 0.2; done; cat {log} >&2; exit 1'
            ),
            env=bridge_env,
        )

    async def run(self, instruction, environment, context) -> None:
        env = await self._tt_prepare(environment) | await self._ca_env(environment)
        await self._start_bridge(environment, env)
        with environment.scoped_exec_env(env):
            await super().run(instruction, environment, context)

    def populate_context_post_run(self, context) -> None:
        super().populate_context_post_run(context)
        path = self.logs_dir / "bridge" / "usage.jsonl"
        records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []
        # The bridge sees every model response, so its usage is the cost
        # record (V-28); Harbor's figure comes from Codex's token counts,
        # which carry no cache writes.
        cost, totals = usage_cost(records)
        context.cost_usd = cost if records else context.cost_usd
        if records:
            context.n_input_tokens = totals["input"] + totals["cache_read"] + totals["cache_write"]
            context.n_cache_tokens = totals["cache_read"]
            context.n_output_tokens = totals["output"]
        metadata = dict(context.metadata or {})
        metadata["bridge"] = {"responses": len(records), "tokens": totals, "cost_usd": cost}
        context.metadata = metadata
        self._tt_metadata(context)
