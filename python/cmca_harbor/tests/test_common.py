import json
from pathlib import Path

import pytest

from cmca_harbor import ChaosClaudeCode, ChaosOpenCode, ChaosPi
from cmca_harbor.claude_code import ChaosClaudeCodeOptions
from cmca_harbor.pi import ChaosPiOptions
from cmca_harbor.common import engine_config, read_events, trial_task_name


def test_options_accept_tt_kwargs():
    opts = ChaosClaudeCodeOptions(attempt_index=2, tt_config_dir="/c", tt_build_dir="/b", max_turns=5)
    assert (opts.attempt_index, opts.tt_config_dir, opts.tt_build_dir, opts.max_turns) == (2, "/c", "/b", 5)
    assert ChaosClaudeCode.options_model is ChaosClaudeCodeOptions
    assert ChaosClaudeCode.name() == "chaos-claude-code"
    pi = ChaosPiOptions(attempt_index=0, tt_config_dir="/c", thinking="low")
    assert (pi.attempt_index, pi.thinking) == (0, "low")
    assert ChaosPi.options_model is ChaosPiOptions


def test_trial_task_name_prefers_trial_config(tmp_path: Path):
    trial = tmp_path / "fix-parser__AbC123"
    (trial / "agent").mkdir(parents=True)
    assert trial_task_name(trial / "agent") == "fix-parser"
    (trial / "config.json").write_text(json.dumps({"task": {"path": "datasets/n/fix_parser"}}))
    assert trial_task_name(trial / "agent") == "fix_parser"


RESOLVED = {
    "schema": "tt-engine/1",
    "seed": "s",
    "trial_id": None,
    "task_id": "t1",
    "attempt": 0,
    "harness": "claude-code",
    "layer": "native",
    "workspace_root": "/app",
    "profile": {
        "schema": "tt-profile/2",
        "name": "clean",
        "base_rate": 0,
        "max_applied_per_trial": 0,
        "warmup_calls": 0,
        "persistence": {},
        "weights": {},
        "class_rate_multipliers": {},
    },
    "parity_set": [],
    "parity_gaps": [],
    "catalog_version": "v1",
    "task": {
        "schema": "tt-task/1",
        "exposure": {"expected_classes": []},
        "poison": [],
        "non_idempotent": [],
        "drift": [],
        "alternatives": [],
        "exempt": {"paths": []},
    },
    "exempt_paths": [],
    "variants": {},
}


def test_engine_config_sets_attempt_and_trial(tmp_path: Path):
    (tmp_path / "t1.json").write_text(json.dumps(RESOLVED))
    cfg = engine_config(tmp_path, "t1", 3, "t1__x")
    assert (cfg["attempt"], cfg["trial_id"]) == (3, "t1__x")
    (tmp_path / "t2.json").write_text(json.dumps(RESOLVED))
    with pytest.raises(ValueError, match="does not match task"):
        engine_config(tmp_path, "t2", 0, "x")


def test_engine_config_rejects_an_unresolved_config(tmp_path: Path):
    raw = {k: v for k, v in RESOLVED.items() if k != "workspace_root"}
    raw["task"] = {"schema": "tt-task/1"}
    (tmp_path / "t1.json").write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="not a resolved tt-engine/1 config"):
        engine_config(tmp_path, "t1", 0, "x")


def test_read_events(tmp_path: Path):
    assert read_events(tmp_path) == []
    (tmp_path / "tt").mkdir()
    (tmp_path / "tt" / "events.jsonl").write_text('{"decision": "apply"}\n\n{"decision": "pass"}\n')
    assert [e["decision"] for e in read_events(tmp_path)] == ["apply", "pass"]


def test_pi_adds_the_extension_flag_only_when_active(tmp_path: Path):
    on = ChaosPi(logs_dir=tmp_path, model_name="anthropic/m", attempt_index=0, tt_config_dir="/c", tt_build_dir="/b")
    assert on.build_cli_flags().endswith("--extension /opt/tt/pi/index.js")
    off = ChaosPi(logs_dir=tmp_path, model_name="anthropic/m")
    assert "--extension" not in off.build_cli_flags()


def test_opencode_adds_the_plugin_only_when_active(tmp_path: Path):
    on = ChaosOpenCode(
        logs_dir=tmp_path,
        model_name="anthropic/m",
        attempt_index=0,
        tt_config_dir="/c",
        tt_build_dir="/b",
        opencode_config={"plugin": ["other"]},
    )
    command = on._build_register_config_command()
    assert '"file:///opt/tt/oc/index.js"' in command and '"other"' in command
    off = ChaosOpenCode(logs_dir=tmp_path, model_name="anthropic/m")
    assert "plugin" not in (off._build_register_config_command() or "")
