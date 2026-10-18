"""Writes ChaosPi's install command, the mcp.json it uploads, and the
opencode.json command ChaosOpenCode runs, for the probe-s-read server, so a
container can run them without Harbor or a model.

    uv run python docs/verification/V-24/emit.py <out dir>
"""

import json
import sys
from pathlib import Path

from harbor.models.task.config import MCPServerConfig

from cmca_harbor import ChaosOpenCode, ChaosPi

out = Path(sys.argv[1])
server = MCPServerConfig(name="tickets", transport="streamable-http", url="http://127.0.0.1:8000/tickets/mcp")
pi = ChaosPi(logs_dir=out, model_name="anthropic/claude-sonnet-5-5", version="1.0.3", mcp_servers=[server])
(out / "pi-install.sh").write_text(pi.install_command() + "\n")
(out / "mcp.json").write_text(json.dumps(pi._build_mcp_config(), indent=2) + "\n")
oc = ChaosOpenCode(logs_dir=out, model_name="anthropic/claude-sonnet-5-5", version="1.18.35", mcp_servers=[server])
(out / "oc-config.sh").write_text(oc._build_register_config_command() + "\n")
