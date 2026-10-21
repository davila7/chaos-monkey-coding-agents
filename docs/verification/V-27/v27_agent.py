"""ChaosFxh with a loopback relay to the V-27 stub model, for conformance runs with no model cost.

fx sends plain HTTP only to a loopback gateway URL; for any other host it
starts TLS and fails with TlsInitializationFailed (observed 2026-10-21 with
http://172.17.0.1:8787). The stub runs on the Docker host, so this agent starts
relay.cjs on 127.0.0.1:8787 in the agent container before the run.

    PYTHONPATH=docs/verification/V-27 harbor run -a v27_agent:StubRelayFxh ... \
      --ae FX_GATEWAY_BASE_URL=http://127.0.0.1:8787 --ae FX_GATEWAY_CHAT_URL=http://127.0.0.1:8787/v1/chat
"""

from pathlib import Path

from cmca_harbor.fxh import ChaosFxh

RELAY = Path(__file__).with_name("relay.cjs")


class StubRelayFxh(ChaosFxh):
    @staticmethod
    def name() -> str:
        return "chaos-fxh-stub-relay"

    async def run(self, instruction, environment, context) -> None:
        await environment.upload_file(RELAY, "/tmp/relay.cjs")
        await self.exec_as_root(environment, command="chmod a+r /tmp/relay.cjs")
        await self.exec_as_agent(environment, command="setsid nohup node /tmp/relay.cjs > /dev/null 2>&1 < /dev/null & sleep 1")
        await super().run(instruction, environment, context)
