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
        "targeted": {},
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
    "sources": {},
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


def test_opencode_trajectory_keeps_failed_tool_text(tmp_path: Path):
    agent = ChaosOpenCode(logs_dir=tmp_path, model_name="anthropic/m")

    def tool(call_id, state):
        return {"type": "tool_use", "part": {"type": "tool", "tool": "read", "callID": call_id, "state": state}}

    events = [
        {"type": "step_start", "timestamp": 1},
        tool("a", {"status": "error", "input": {"filePath": "/app/x"}, "error": "EACCES: permission denied"}),
        tool("b", {"status": "completed", "input": {"filePath": "/app/y"}, "output": "y"}),
        {"type": "step_finish", "part": {}},
    ]
    trajectory = agent._convert_events_to_trajectory(events).to_json_dict()
    results = {r["source_call_id"]: r["content"] for s in trajectory["steps"] for r in ((s.get("observation") or {}).get("results") or [])}
    assert results == {"a": "EACCES: permission denied", "b": "y"}


class _RecordingEnv:
    def __init__(self):
        self.uploads = []

    async def upload_file(self, src, dst):
        self.uploads.append((Path(src), dst))


def test_extra_ca_cert_is_uploaded_and_exposed_to_node(tmp_path: Path):
    import asyncio

    pem = tmp_path / "ca.pem"
    pem.write_text("-----BEGIN CERTIFICATE-----\n")
    env = _RecordingEnv()
    agent = ChaosClaudeCode(logs_dir=tmp_path, model_name="m", extra_ca_cert=str(pem))
    commands = []

    async def fake_root(environment, command, **_):
        commands.append(command)

    agent.exec_as_root = fake_root
    assert asyncio.run(agent._ca_env(env)) == {"NODE_EXTRA_CA_CERTS": "/opt/tt/ca.crt"}
    assert env.uploads == [(pem, "/opt/tt/ca.crt")]
    assert ChaosClaudeCode(logs_dir=tmp_path, model_name="m").options.extra_ca_cert is None
    assert asyncio.run(ChaosClaudeCode(logs_dir=tmp_path, model_name="m")._ca_env(env)) == {}


def _tickets_server():
    from harbor.models.task.config import MCPServerConfig

    return MCPServerConfig(name="tickets", transport="streamable-http", url="http://127.0.0.1:8000/tickets/mcp")


def test_pi_mcp_config_declares_every_server_directly(tmp_path: Path):
    from harbor.models.task.config import MCPServerConfig

    stdio = MCPServerConfig(name="local", transport="stdio", command="srv", args=["-q"])
    agent = ChaosPi(logs_dir=tmp_path, model_name="anthropic/m", version="1.0.3", mcp_servers=[_tickets_server(), stdio])
    assert agent._build_mcp_config() == {
        "autoEnableCodemode": False,
        "mcpServers": {
            "tickets": {"url": "http://127.0.0.1:8000/tickets/mcp", "exposure": "direct"},
            "local": {"command": "srv", "args": ["-q"], "exposure": "direct"},
        },
    }


def test_pi_install_pins_the_sibling_packages(tmp_path: Path):
    from cmca_harbor.pi import INSTALL_DIR, PIN_SIBLINGS_JS

    command = ChaosPi(logs_dir=tmp_path, model_name="anthropic/m", version="1.0.3", mcp_servers=[_tickets_server()]).install_command()
    assert f"cd {INSTALL_DIR} && node -e" in command
    assert "@earendil-works/pi-coding-agent 1.0.3 && npm install --ignore-scripts" in command
    assert "overrides" in PIN_SIBLINGS_JS and command.endswith("pi --version")
    assert "pi-mcp-adapter" not in command
    with pytest.raises(ValueError, match="pinned"):
        ChaosPi(logs_dir=tmp_path, model_name="anthropic/m").install_command()


def test_pi_run_skips_the_adapter_and_points_pi_at_its_mcp_json(tmp_path: Path, monkeypatch):
    import asyncio
    import contextlib

    from harbor.agents.installed.pi import Pi

    agent = ChaosPi(logs_dir=tmp_path, model_name="anthropic/m", version="1.0.3", mcp_servers=[_tickets_server()])
    seen = {}

    async def write(environment):
        seen["config"] = agent._build_mcp_config()

    async def run(self, instruction, environment, context):
        seen["servers_during_run"] = list(self.mcp_servers)

    class Env:
        @contextlib.contextmanager
        def scoped_exec_env(self, env):
            seen["env"] = dict(env)
            yield

    agent._write_mcp_config = write
    monkeypatch.setattr(Pi, "run", run)
    asyncio.run(agent.run("go", Env(), None))
    assert seen["servers_during_run"] == []
    assert seen["env"] == {"PI_CODING_AGENT_DIR": "/tmp/harbor-pi-agent"}
    assert seen["config"]["mcpServers"]["tickets"]["exposure"] == "direct"
    assert [s.name for s in agent.mcp_servers] == ["tickets"]

    seen.clear()
    plain = ChaosPi(logs_dir=tmp_path, model_name="anthropic/m", version="1.0.3")
    asyncio.run(plain.run("go", Env(), None))
    assert seen == {"servers_during_run": [], "env": {}}
