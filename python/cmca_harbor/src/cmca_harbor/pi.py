from harbor.agents.installed.pi import Pi, PiOptions

from cmca_harbor.common import REMOTE_ROOT, TtAgentMixin, TtOptions


class ChaosPiOptions(PiOptions, TtOptions):
    pass


class ChaosPi(TtAgentMixin, Pi):
    """Harbor's Pi agent with the extension passed through `--extension`."""

    options_model = ChaosPiOptions
    HARNESS_DIR = "pi"

    @staticmethod
    def name() -> str:
        return "chaos-pi"

    def build_cli_flags(self) -> str:
        flags = super().build_cli_flags()
        if not self._tt_active():
            return flags
        ext = f"--extension {REMOTE_ROOT}/{self.HARNESS_DIR}/index.js"
        return f"{flags} {ext}".strip()

    async def run(self, instruction, environment, context) -> None:
        env = await self._tt_prepare(environment)
        with environment.scoped_exec_env(env):
            await super().run(instruction, environment, context)

    def populate_context_post_run(self, context) -> None:
        super().populate_context_post_run(context)
        self._tt_metadata(context)
