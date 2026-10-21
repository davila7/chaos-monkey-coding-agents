"""fxh on Track N: fx installed from the fork with tool call commands (D-0040).

fxh is fx 0.0.13 plus commands that run before and after each built-in tool
call, read from `~/.fx/settings.json` (FORK.md in davila7/fxh). The binary is
installed as `fx`, so Harbor's run command, the session layout and the ATIF
conversion are the ones `ChaosFx` uses on Track S.
"""

import shlex
from pathlib import Path
from typing import Any

from pydantic import Field

from cmca_harbor.common import REMOTE_ROOT, TtAgentMixin
from cmca_harbor.fx import ChaosFx, ChaosFxOptions

RELEASES = "https://github.com/davila7/fxh/releases/download"
# sha256 of the binary inside `fxh-v<version>-linux-<arch>.tar.gz`. The fork
# builds reproducibly (FORK.md), so a local ReleaseSafe build of the tagged
# commit has the same hash as the release. The binary embeds the short commit
# id, so the release (merge commit 920a081) differs from the V-27 build of
# e6cc054, which has the same source tree (V-27, "Release binary").
BINARIES = {
    "0.0.13-h1": {
        "x86_64": "574acd4d65da41e6e88980aa4381651cac1d1a1268c276b75a2429a159de9189",
    },
}
# Built-in tools the injector maps to a capability class (packages/injector-fxh).
TOOLS = "read_file|write_file|edit_file|grep_files|glob_files|shell"
# Agent-visible, so neutral (SPEC 7.2).
REMOTE_ARCHIVE = "/tmp/fx-release.tar.gz"


class ChaosFxhOptions(ChaosFxOptions):
    # Host path of a release archive to upload instead of downloading it,
    # checked against the same pin (V-27 ran before the release existed).
    fxh_archive: str | None = Field(default=None)


class ChaosFxh(TtAgentMixin, ChaosFx):
    options_model = ChaosFxhOptions
    HARNESS_DIR = "fxh"

    @staticmethod
    def name() -> str:
        return "chaos-fxh"

    def _settings(self) -> dict[str, Any]:
        settings = super()._settings()
        if self._tt_active():
            command = f"node {REMOTE_ROOT}/{self.HARNESS_DIR}/index.cjs"
            group = [{"matcher": TOOLS, "hooks": [{"type": "command", "command": command, "timeout": 30}]}]
            settings["hooks"] = {"PreToolUse": group, "PostToolUse": group}
        return settings

    def install_script(self, binary_sha: str, local_archive: bool) -> str:
        version = self._version
        fetch = (
            f"mv {REMOTE_ARCHIVE} $t/a.tgz"
            if local_archive
            else f'curl -fsSL {RELEASES}/v{version}/fxh-v{version}-linux-$a.tar.gz -o $t/a.tgz'
        )
        # The archive also holds FORK.md, which names the experiment; only the
        # binary leaves the temporary directory.
        return (
            "set -euo pipefail; "
            'case "$(uname -m)" in amd64) a=x86_64;; *) a=$(uname -m);; esac; '
            '[ "$a" = x86_64 ] || { echo "unsupported arch $a" >&2; exit 1; }; '
            f"t=$(mktemp -d); {fetch}; tar -xzf $t/a.tgz -C $t; "
            f'b=$t/fxh-v{version}-linux-$a/fxh; echo "{binary_sha}  $b" | sha256sum -c -; '
            'mkdir -p "$HOME/.local/bin"; mv $b "$HOME/.local/bin/fx"; rm -rf $t; '
            f"{self._PATH_EXPORT}; fx --version"
        )

    async def install(self, environment) -> None:
        version = self._version or ""
        sha = BINARIES.get(version, {}).get("x86_64")
        if not sha:
            raise ValueError(f"fxh {version!r}: no pinned binary checksum; add it to cmca_harbor.fxh.BINARIES")
        # Node runs the injector, as for the Claude Code and OpenCode agents.
        await self.ensure_system_dependencies(environment, ("curl", "bash", "ca_certificates", "tar", "coreutils", "tmux", "nodejs"))
        await self._trust_extra_ca(environment)
        local = self.options.fxh_archive
        if local:
            await environment.upload_file(Path(local), REMOTE_ARCHIVE)
            owner = environment.default_user
            if owner is not None:
                await self.exec_as_root(environment, command=f"chown {shlex.quote(str(owner))} {REMOTE_ARCHIVE}")
        await self.exec_as_agent(environment, command=self.install_script(sha, bool(local)))
        await self._configure(environment)

    async def run(self, instruction, environment, context) -> None:
        env = await self._tt_prepare(environment)
        with environment.scoped_exec_env(env):
            await super().run(instruction, environment, context)

    def populate_context_post_run(self, context) -> None:
        super().populate_context_post_run(context)
        self._tt_metadata(context)

