import json
from pathlib import Path

import pytest

from cmca_harbor import ChaosClaudeCode
from cmca_harbor.claude_code import ChaosClaudeCodeOptions
from cmca_harbor.common import engine_config, read_events, trial_task_name


def test_options_accept_tt_kwargs():
    opts = ChaosClaudeCodeOptions(attempt_index=2, tt_config_dir="/c", tt_build_dir="/b", max_turns=5)
    assert (opts.attempt_index, opts.tt_config_dir, opts.tt_build_dir, opts.max_turns) == (2, "/c", "/b", 5)
    assert ChaosClaudeCode.options_model is ChaosClaudeCodeOptions
    assert ChaosClaudeCode.name() == "chaos-claude-code"


def test_trial_task_name_prefers_trial_config(tmp_path: Path):
    trial = tmp_path / "fix-parser__AbC123"
    (trial / "agent").mkdir(parents=True)
    assert trial_task_name(trial / "agent") == "fix-parser"
    (trial / "config.json").write_text(json.dumps({"task": {"path": "datasets/n/fix_parser"}}))
    assert trial_task_name(trial / "agent") == "fix_parser"


def test_engine_config_sets_attempt_and_trial(tmp_path: Path):
    (tmp_path / "t1.json").write_text(json.dumps({"schema": "tt-engine/1", "task_id": "t1", "attempt": 0}))
    cfg = engine_config(tmp_path, "t1", 3, "t1__x")
    assert (cfg["attempt"], cfg["trial_id"]) == (3, "t1__x")
    (tmp_path / "t2.json").write_text(json.dumps({"schema": "tt-engine/1", "task_id": "other"}))
    with pytest.raises(ValueError):
        engine_config(tmp_path, "t2", 0, "x")


def test_read_events(tmp_path: Path):
    assert read_events(tmp_path) == []
    (tmp_path / "tt").mkdir()
    (tmp_path / "tt" / "events.jsonl").write_text('{"decision": "apply"}\n\n{"decision": "pass"}\n')
    assert [e["decision"] for e in read_events(tmp_path)] == ["apply", "pass"]
