import shlex
from typing import Any

from harbor.agents.installed.node_install import nvm_node_install_snippet
from harbor.agents.installed.pi import _PI_CONFIG_DIR_ENV, _REMOTE_PI_CONFIG_DIR, Pi, PiOptions

from cmca_harbor.common import REMOTE_ROOT, TtAgentMixin, TtOptions

# Agent-visible, so neutral (SPEC 7.2).
INSTALL_DIR = "/tmp/pi-pinned"

# Writes a package.json that installs the harness at `version` with every
# package of its npm scope that it depends on, directly or through a sibling,
# overridden to the same version. Pi 1.0.3 depends on its siblings with
# `^1.0.3`, and a plain install on 2026-10-18 resolved them to 1.3.0, on
# which `pi --version` fails (D-0038).
PIN_SIBLINGS_JS = """
const { execFileSync } = require("child_process");
const fs = require("fs");
const [pkg, version] = process.argv.slice(1);
const scope = pkg.split("/")[0] + "/";
const overrides = {};
const queue = [pkg];
const seen = new Set();
while (queue.length) {
  const p = queue.shift();
  if (seen.has(p)) continue;
  seen.add(p);
  const out = execFileSync("npm", ["view", `${p}@${version}`, "dependencies", "--json"], { encoding: "utf8" }).trim();
  for (const dep of Object.keys(out ? JSON.parse(out) : {})) {
    if (dep.startsWith(scope)) {
      overrides[dep] = version;
      queue.push(dep);
    }
  }
}
fs.writeFileSync("package.json", JSON.stringify({ private: true, dependencies: { [pkg]: version }, overrides }, null, 1));
""".strip()


class ChaosPiOptions(PiOptions, TtOptions):
    pass


class ChaosPi(TtAgentMixin, Pi):
    """Harbor's Pi agent with the extension passed through `--extension`, a
    pinned install, and Pi's built-in MCP support with direct exposure.

    Harbor 0.24.0 serves MCP to Pi through `pi-mcp-adapter`, which needs Pi
    below 0.86. Pi has MCP built in since 0.99.0 and reads servers from
    `mcp.json` in its agent directory (D-0038 item 1).
    """

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

    def install_command(self) -> str:
        if not self._version or self._version == "latest":
            raise ValueError("ChaosPi installs a pinned Pi version; pass --ak version=<x.y.z>")
        pkg = self._package_name()
        return (
            "set -euo pipefail; "
            f"{nvm_node_install_snippet()} && "
            f"mkdir -p {INSTALL_DIR} && cd {INSTALL_DIR} && "
            f"node -e {shlex.quote(PIN_SIBLINGS_JS)} {shlex.quote(pkg)} {shlex.quote(self._version)} && "
            "npm install --ignore-scripts --no-audit --no-fund && "
            f'ln -sf {INSTALL_DIR}/node_modules/.bin/pi "$(npm prefix -g)/bin/pi" && '
            "cd / && pi --version"
        )

    async def install(self, environment) -> None:
        await self.ensure_system_dependencies(environment, ("curl",))
        ca = await self._ca_env_and_system_bundle(environment)
        with environment.scoped_exec_env(ca):
            await self.exec_as_agent(environment, command=self.install_command())

    def _build_mcp_config(self) -> dict[str, Any]:
        # Direct exposure declares MCP tools to the model like built-in tools,
        # as under cc-claude and fx-claude; codemode would put a model-written
        # script between the model and every result (D-0038 item 1).
        servers: dict[str, dict[str, Any]] = {}
        for server in self.mcp_servers:
            if server.transport == "stdio":
                entry: dict[str, Any] = {"command": server.command, "args": list(server.args)}
            else:
                entry = {"url": server.url}
            servers[server.name] = {**entry, "exposure": "direct"}
        return {"autoEnableCodemode": False, "mcpServers": servers}

    async def run(self, instruction, environment, context) -> None:
        env = await self._tt_prepare(environment) | await self._ca_env(environment)
        servers = self.mcp_servers
        if servers:
            await self._write_mcp_config(environment)
            env[_PI_CONFIG_DIR_ENV] = _REMOTE_PI_CONFIG_DIR.as_posix()
        # Harbor's run adds the adapter extension whenever servers are set.
        self.mcp_servers = []
        try:
            with environment.scoped_exec_env(env):
                await super().run(instruction, environment, context)
        finally:
            self.mcp_servers = servers

    def populate_context_post_run(self, context) -> None:
        super().populate_context_post_run(context)
        self._tt_metadata(context)
