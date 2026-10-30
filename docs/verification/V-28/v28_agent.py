"""ChaosCodex with its bridge pointed at the V-28 stub model, for conformance runs with no model cost.

    PYTHONPATH=docs/verification/V-28 harbor run -a v28_agent:StubCodex ...

STUB_URL names the stub as the agent container reaches it (default
http://172.17.0.1:8788, the Docker host). The bridge and Codex are the same
as in ChaosCodex; only the Messages API endpoint and key differ.
"""

import os

from cmca_harbor.codex import ChaosCodex


class StubCodex(ChaosCodex):
    @staticmethod
    def name() -> str:
        return "chaos-codex-stub"

    def _model_env(self) -> dict[str, str]:
        return {"ANTHROPIC_BASE_URL": os.environ.get("STUB_URL", "http://172.17.0.1:8788"), "ANTHROPIC_API_KEY": "stub"}
