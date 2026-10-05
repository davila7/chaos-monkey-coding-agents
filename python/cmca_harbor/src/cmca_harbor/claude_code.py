import json
import shlex
import tempfile
from pathlib import Path

from harbor.agents.installed.claude_code import ClaudeCode, ClaudeCodeOptions

from cmca_harbor.common import (
    REMOTE_CONFIG,
    REMOTE_LOG,
    REMOTE_LOG_DIR,
    REMOTE_ROOT,
    REMOTE_STATE,
    TtOptions,
    engine_config,
    read_events,
    trial_task_name,
)

PLUGIN_DIR = f"{REMOTE_ROOT}/cc"


class ChaosClaudeCodeOptions(ClaudeCodeOptions, TtOptions):
    pass


class ChaosClaudeCode(ClaudeCode):
    """Harbor's Claude Code agent with the `tool.call` plugin loaded headlessly.

    The plugin and `tt-decide` come from `tt_build_dir`; the per-task engine
    config from `tt_config_dir`. Without `tt_config_dir` the harness runs
    unmodified, which is the `clean` baseline with identical installation.
    """

    options_model = ChaosClaudeCodeOptions

    @staticmethod
    def name() -> str:
        return "chaos-claude-code"

    async def install(self, environment) -> None:
        # Harbor's default installer fetches a bootstrap script from a host
        # that some egress policies deny; npm also makes the version explicit.
        if await self._installed_claude_satisfies_version(environment):
            return
        await self.ensure_system_dependencies(environment, ("curl", "bash", "nodejs", "npm", "procps"))
        pkg = "@anthropic-ai/claude-code" + (f"@{self._version}" if self._version else "")
        await self.exec_as_root(environment, command=f"npm install -g {shlex.quote(pkg)} && claude --version")

    async def run(self, instruction, environment, context) -> None:
        opts = self.options
        if opts.tt_config_dir:
            if opts.attempt_index is None:
                raise ValueError("attempt_index is required when tt_config_dir is set")
            if not opts.tt_build_dir:
                raise ValueError("tt_build_dir is required when tt_config_dir is set")
            task = trial_task_name(self.logs_dir)
            cfg = engine_config(Path(opts.tt_config_dir), task, opts.attempt_index, self.logs_dir.parent.name)
            await self._upload_injector(environment, Path(opts.tt_build_dir), cfg)
            self._resolved_env_vars.update(
                {
                    "CLAUDE_CODE_PLUGIN_DIRS": PLUGIN_DIR,
                    "TT_CONFIG": REMOTE_CONFIG,
                    "TT_STATE": REMOTE_STATE,
                    "TT_LOG": REMOTE_LOG,
                }
            )
        await super().run(instruction, environment, context)

    async def _upload_injector(self, environment, build_dir: Path, cfg: dict) -> None:
        for required in ("bin/tt-decide.cjs", "cc/hooks/register.js", "cc/.claude-plugin/plugin.json"):
            if not (build_dir / required).exists():
                raise FileNotFoundError(f"{build_dir / required} missing; run `pnpm build`")
        await self.exec_as_root(environment, command=f"mkdir -p {REMOTE_ROOT} {REMOTE_LOG_DIR}")
        await environment.upload_dir(build_dir / "bin", f"{REMOTE_ROOT}/bin")
        await environment.upload_dir(build_dir / "cc", PLUGIN_DIR)
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp) / "config.json"
            local.write_text(json.dumps(cfg))
            await environment.upload_file(local, REMOTE_CONFIG)
        owner = environment.default_user
        chown = f"chown -R {shlex.quote(str(owner))} {REMOTE_ROOT} {REMOTE_LOG_DIR} && " if owner is not None else ""
        await self.exec_as_root(
            environment,
            command=f"{chown}mkdir -p {REMOTE_STATE} && chmod -R a+rX {REMOTE_ROOT}",
        )

    def populate_context_post_run(self, context) -> None:
        super().populate_context_post_run(context)
        events = read_events(self.logs_dir)
        metadata = dict(context.metadata or {})
        metadata["tt"] = {
            "events": len(events),
            "delivered": sum(1 for e in events if e.get("decision") == "apply"),
            "errors": sum(1 for e in events if e.get("decision") == "error"),
        }
        context.metadata = metadata
