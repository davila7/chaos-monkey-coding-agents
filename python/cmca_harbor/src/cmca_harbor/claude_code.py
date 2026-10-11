import shlex

from harbor.agents.installed.claude_code import ClaudeCode, ClaudeCodeOptions

from cmca_harbor.common import REMOTE_ROOT, TtAgentMixin, TtOptions


class ChaosClaudeCodeOptions(ClaudeCodeOptions, TtOptions):
    pass


class ChaosClaudeCode(TtAgentMixin, ClaudeCode):
    """Harbor's Claude Code agent with the `tool.call` plugin loaded headlessly
    through `CLAUDE_CODE_PLUGIN_DIRS`."""

    options_model = ChaosClaudeCodeOptions
    HARNESS_DIR = "cc"

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
        ca = await self._ca_env(environment)
        with environment.scoped_exec_env(ca):
            await self.exec_as_root(environment, command=f"npm install -g {shlex.quote(pkg)} && claude --version")

    async def run(self, instruction, environment, context) -> None:
        env = await self._tt_prepare(environment)
        ca = await self._ca_env(environment)
        if env:
            env["CLAUDE_CODE_PLUGIN_DIRS"] = f"{REMOTE_ROOT}/{self.HARNESS_DIR}"
            # The local probe on 2026-10-10 passed this; whether 2.1.x loads
            # function hooks without it is not yet verified (V-01).
            env["CLAUDE_CODE_ENABLE_FUNCTION_HOOKS"] = "1"
        with environment.scoped_exec_env(env | ca):
            await super().run(instruction, environment, context)

    def populate_context_post_run(self, context) -> None:
        super().populate_context_post_run(context)
        self._tt_metadata(context)
