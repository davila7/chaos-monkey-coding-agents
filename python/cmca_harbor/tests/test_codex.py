import json

import pytest

from cmca_harbor.codex import CATALOG, PROVIDER, TOOLS, ChaosCodex, usage_cost


def agent(tmp_path, **tt):
    return ChaosCodex(logs_dir=tmp_path, model_name="claude-sonnet-5-5", version="0.163.0", **tt)


def test_config_routes_codex_to_the_bridge(tmp_path):
    config = agent(tmp_path)._build_effective_config()
    assert config["model_provider"] == PROVIDER
    provider = config["model_providers"][PROVIDER]
    assert provider["base_url"] == "http://127.0.0.1:18080/v1"
    assert provider["wire_api"] == "responses" and provider["supports_websockets"] is False
    assert config["web_search"] == "disabled"
    assert config["features"]["multi_agent"] is False
    assert "hooks" not in config and "hooks" not in config["features"]
    assert "--dangerously-bypass-hook-trust" not in agent(tmp_path).build_cli_flags()


def test_hooks_run_the_injector_only_when_active(tmp_path):
    on = agent(tmp_path, attempt_index=0, tt_config_dir="/c", tt_build_dir="/b")
    config = on._build_effective_config()
    assert config["features"]["hooks"] is True
    for event in ("PreToolUse", "PostToolUse"):
        (group,) = config["hooks"][event]
        assert group["matcher"] == TOOLS
        assert group["hooks"] == [{"type": "command", "command": "node /opt/tt/codex/index.cjs", "timeout": 30}]
    assert on.build_cli_flags().count("--dangerously-bypass-hook-trust") == 1


def test_catalog_declares_apply_patch_for_the_model():
    (entry,) = json.loads(CATALOG.read_text())["models"]
    assert entry["slug"] == "claude-sonnet-5-5"
    assert entry["apply_patch_tool_type"] == "freeform"
    assert entry["shell_type"] == "unified_exec"


def test_model_env_never_carries_a_base_url(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://elsewhere")
    assert agent(tmp_path)._model_env() == {"ANTHROPIC_API_KEY": "k"}
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    with pytest.raises(ValueError):
        agent(tmp_path)._model_env()


def test_usage_cost_at_list_prices():
    records = [
        {"model": "claude-sonnet-5-5", "usage": {"input_tokens": 1_000_000, "output_tokens": 100_000, "cache_read_input_tokens": 2_000_000, "cache_creation_input_tokens": 400_000}},
        {"model": "claude-sonnet-5-5", "usage": {"input_tokens": 0, "output_tokens": 0}},
    ]
    cost, totals = usage_cost(records)
    assert cost == pytest.approx(2.00 + 1.00 + 0.20 + 1.00)
    assert totals == {"input": 1_000_000, "output": 100_000, "cache_read": 2_000_000, "cache_write": 400_000}
    assert usage_cost([{"model": "other", "usage": {}}])[0] is None
