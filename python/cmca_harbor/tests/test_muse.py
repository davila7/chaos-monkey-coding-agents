import json
from types import SimpleNamespace

import pytest

from cmca_harbor.conformance import muse_inner
from cmca_harbor.muse import BINARIES, ChaosMuse, redact_builtin_prompts, usage_cost

PIN = "1.4.14-R7309.1"


def agent(tmp_path, **kw):
    return ChaosMuse(logs_dir=tmp_path, model_name="meta/muse-spark-1.3", version=PIN, **kw)


def test_every_pinned_version_has_both_linux_checksums():
    for sums in BINARIES.values():
        assert set(sums) == {"x86", "aarch64"}
        assert all(len(v) == 64 for v in sums.values())


def test_install_checks_the_binary_before_placing_it(tmp_path):
    script = agent(tmp_path).install_script()
    assert f"version={PIN}&file=muse-$a-linux" in script
    assert script.index("sha256sum -c") < script.index('install -m 755 $t/muse "$HOME/.local/bin/muse"')
    assert "MUSE_NO_AUTO_UPDATE=1 muse --version" in script


def test_unpinned_version_is_refused(tmp_path):
    with pytest.raises(ValueError, match="no pinned binary"):
        ChaosMuse(logs_dir=tmp_path, model_name="meta/muse-spark-1.3", version="1.4.15").install_script()


def test_flags_select_meta_and_standard_mode(tmp_path):
    assert agent(tmp_path).build_cli_flags() == "--provider meta --contributor-mode off"
    assert agent(tmp_path, disable_reminders=True).build_cli_flags().endswith("--disable-reminders")


def test_settings_register_the_injector_only_when_active(tmp_path):
    assert "hooks" not in agent(tmp_path)._build_effective_config()
    on = agent(tmp_path, attempt_index=0, tt_config_dir="/c", tt_build_dir="/b")._build_effective_config()
    assert set(on["hooks"]) == {"PreToolUse", "PostToolUse", "PostToolUseFailure"}
    (group,) = on["hooks"]["PreToolUse"]
    assert group["matcher"] == "*"
    (hook,) = group["hooks"]
    # Muse clears the hook environment (V-29), so the paths travel in the command.
    assert hook["command"].startswith("env TT_CONFIG=/opt/tt/config.json TT_STATE=/opt/tt/state TT_LOG=/logs/agent/tt/events.jsonl")
    assert hook["command"].endswith("node /opt/tt/muse/index.cjs")


def test_version_is_the_build_id(tmp_path):
    assert agent(tmp_path).parse_version("Muse Code 1.4.14 (1.4.14-R7309.1)\n") == PIN


def test_cost_uses_meta_list_prices():
    # The smoke trial of 2026-10-31: 52,026 input of which 25,841 cached, 451 output.
    assert usage_cost("muse-spark-1.3", 52026, 25841, 451) == pytest.approx(0.03852415)
    assert usage_cost("other", 1, 0, 1) is None
    assert usage_cost("muse-spark-1.3", None, None, None) is None


def test_metadata_counts_reminder_tasks_and_keeps_run_usage(tmp_path):
    a = agent(tmp_path)
    lines = [
        {"payload_type": "task.lifecycle.proposed", "payload": {"event": {"task_kind": "reminder.agent.goal-reminder"}}},
        {"payload_type": "task.lifecycle.proposed", "payload": {"event": {"task_kind": "model.meta.response"}}},
        {"payload_type": "run.usage", "payload": {"calls": 2, "children_included": False}},
    ]
    (tmp_path / a._OUTPUT_FILENAME).write_text("\n".join(json.dumps(x) for x in lines) + "\nnot json\n")
    context = SimpleNamespace(metadata=None, n_input_tokens=None, n_cache_tokens=None, n_output_tokens=None, cost_usd=None)
    a.populate_context_post_run(context)
    assert context.metadata["muse"] == {"run_usage": [{"calls": 2, "children_included": False}], "reminder_tasks": 1}
    assert context.cost_usd is None


def test_inner_output_of_muse_results():
    shell = json.dumps({"chunk_id": "exec-1-1", "exit_code": 0, "output": "a\n", "truncated": False}, indent=2)
    assert muse_inner("bash", shell) == "a\n"
    assert muse_inner("read_file", "Read text file `a.txt`.\n1|x\n2|y") == "x\ny"
    assert muse_inner("read_file", "Read text file `a.txt`.") == ""
    assert muse_inner("write_file", "wrote 1 bytes") == "wrote 1 bytes"


def test_track_s_servers_reach_muse_settings(tmp_path):
    from harbor.models.task.config import MCPServerConfig

    assert ChaosMuse.capabilities.mcp_servers
    a = ChaosMuse(
        logs_dir=tmp_path,
        model_name="meta/muse-spark-1.3",
        version=PIN,
        mcp_servers=[MCPServerConfig(name="tickets", transport="streamable-http", url="http://gateway:8080/mcp")],
    )
    assert a._build_effective_config()["mcp_servers"]["tickets"] == {
        "enabled": True,
        "mode": "required",
        "transport": "streamable_http",
        "url": "http://gateway:8080/mcp",
    }


def test_builtin_prompts_are_redacted_everywhere():
    t = {
        "steps": [{"source": "user", "message": "task"}, {"source": "system", "message": "You are the harness."}],
        "subagent_trajectories": [{"steps": [{"source": "system", "message": "You watch another agent."}]}],
    }
    assert redact_builtin_prompts(t) == 2
    assert t["steps"][0]["message"] == "task"
    assert t["steps"][1]["message"].startswith("[redacted: Muse Code built-in prompt, sha256 ")
    assert "You watch" not in json.dumps(t)
    assert redact_builtin_prompts(t) == 0
