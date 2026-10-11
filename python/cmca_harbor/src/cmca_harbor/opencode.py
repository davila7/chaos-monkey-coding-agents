from harbor.agents.installed.opencode import OpenCode, OpenCodeOptions

from cmca_harbor.common import REMOTE_ROOT, TtAgentMixin, TtOptions


class ChaosOpenCodeOptions(OpenCodeOptions, TtOptions):
    pass


class ChaosOpenCode(TtAgentMixin, OpenCode):
    """Harbor's OpenCode agent with the plugin added to the written opencode.json."""

    options_model = ChaosOpenCodeOptions
    HARNESS_DIR = "oc"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self._tt_active():
            plugins = list(self._opencode_config.get("plugin", []))
            plugins.append(f"file://{REMOTE_ROOT}/{self.HARNESS_DIR}/index.js")
            self._opencode_config = {**self._opencode_config, "plugin": plugins}

    @staticmethod
    def name() -> str:
        return "chaos-opencode"

    async def run(self, instruction, environment, context) -> None:
        env = await self._tt_prepare(environment)
        with environment.scoped_exec_env(env):
            await super().run(instruction, environment, context)

    def _convert_events_to_trajectory(self, events):
        # Harbor records a tool part's `output` only. A failed call, including
        # one an injector hook failed, carries its text in `error` (V-06).
        return super()._convert_events_to_trajectory([_error_as_output(e) for e in events])

    def populate_context_post_run(self, context) -> None:
        super().populate_context_post_run(context)
        self._tt_metadata(context)


def _error_as_output(event):
    part = event.get("part")
    state = part.get("state") if isinstance(part, dict) else None
    if not (isinstance(state, dict) and state.get("status") == "error" and state.get("output") is None):
        return event
    return {**event, "part": {**part, "state": {**state, "output": state.get("error", "")}}}
