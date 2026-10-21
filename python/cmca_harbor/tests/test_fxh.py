from cmca_harbor.fxh import BINARIES, TOOLS, ChaosFxh


def test_every_pinned_version_has_a_binary_checksum():
    for sums in BINARIES.values():
        assert set(sums) == {"x86_64"}
        assert all(len(v) == 64 for v in sums.values())


def test_settings_register_the_injector_only_when_active(tmp_path):
    on = ChaosFxh(logs_dir=tmp_path, model_name="anthropic/m", version="0.0.13-h1", reasoning_effort="medium", attempt_index=0, tt_config_dir="/c", tt_build_dir="/b")
    settings = on._settings()
    assert settings["effort"] == "medium"
    for event in ("PreToolUse", "PostToolUse"):
        (group,) = settings["hooks"][event]
        assert group["matcher"] == TOOLS
        assert group["hooks"] == [{"type": "command", "command": "node /opt/tt/fxh/index.cjs", "timeout": 30}]
    off = ChaosFxh(logs_dir=tmp_path, model_name="anthropic/m", version="0.0.13-h1", reasoning_effort="medium")
    assert off._settings() == {"effort": "medium"}


def test_install_keeps_only_the_checked_binary(tmp_path):
    agent = ChaosFxh(logs_dir=tmp_path, model_name="anthropic/m", version="0.0.13-h1")
    script = agent.install_script("a" * 64, local_archive=False)
    assert "https://github.com/davila7/fxh/releases/download/v0.0.13-h1/fxh-v0.0.13-h1-linux-$a.tar.gz" in script
    assert f'echo "{"a" * 64}  $b" | sha256sum -c -' in script
    assert script.index("sha256sum -c") < script.index('mv $b "$HOME/.local/bin/fx"') < script.index("rm -rf $t")
    local = agent.install_script("a" * 64, local_archive=True)
    assert "curl" not in local and "mv /tmp/fx-release.tar.gz $t/a.tgz" in local
