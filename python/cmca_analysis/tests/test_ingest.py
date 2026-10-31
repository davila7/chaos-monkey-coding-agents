import json
import tomllib

import pytest

from cmca_analysis.ingest import DATASETS, MCP_SERVERS, Call, args_hash, bare_name, join
from cmca_analysis.reconcile import delivered


@pytest.mark.parametrize(
    "tool",
    [
        "mcp__tickets__get_ticket",  # Claude Code, Pi 1.0.3
        "mcp_tickets_get_ticket",  # fx 0.0.13
        "tickets_get_ticket",  # OpenCode 1.18.35 (V-25)
        "get_ticket",
    ],
)
def test_every_harness_prefix_is_stripped(tool):
    assert bare_name(tool) == "get_ticket"


def test_server_named_like_its_tool():
    assert bare_name("deploy_deploy") == "deploy"
    assert bare_name("mcp__deploy__deploy") == "deploy"


@pytest.mark.parametrize("tool", ["Bash", "read", "todowrite", "webfetch", "list_services", "search_docs", "get_doc"])
def test_builtin_and_bare_names_are_kept(tool):
    assert bare_name(tool) == tool


def test_known_servers_are_the_ones_track_s_declares():
    declared = {
        s["name"]
        for dataset in DATASETS
        for toml in dataset.glob("*/task.toml")
        for s in tomllib.loads(toml.read_text()).get("environment", {}).get("mcp_servers", [])
    }
    assert declared == set(MCP_SERVERS)


@pytest.mark.parametrize("prefix", ["mcp__tickets__", "tickets_"])
def test_gateway_records_join_pi_and_opencode_calls(prefix):
    calls = [Call(i, i, i, f"{prefix}{name}", {}, "") for i, name in enumerate(["get_ticket", "add_comment", "get_ticket"])]
    events = [{"seq": i, "tool_name": n, "decision": "pass"} for i, n in enumerate(["get_ticket", "add_comment", "get_ticket"])]
    assert [c.index for _, c in join(events, calls)] == [0, 1, 2]


FX_NOT_RUN = json.dumps(
    {"error": {"type": "tool_execution_failed", "tool_name": "shell",
               "message": "Tool arguments ended before the JSON was complete, so fx did not run the call. The conversation shows its arguments as {}.",
               "details": {"failure": "truncated"}}},
    separators=(",", ":"),
)


def test_join_skips_calls_fx_did_not_run():
    observations = ["a", FX_NOT_RUN, "b"]
    calls = [Call(i, i, i, "shell", {}, o) for i, o in enumerate(observations)]
    events = [{"seq": i, "tool_name": "shell", "decision": "pass"} for i in range(2)]
    assert [c.index for _, c in join(events, calls)] == [0, 2]


def test_join_skips_fx_shell_calls_on_a_started_command():
    actions = ["run", "interact", None, "stop", "run"]
    calls = [Call(i, i, i, "shell", {} if a is None else {"action": a}, "x") for i, a in enumerate(actions)]
    events = [{"seq": i, "tool_name": "shell", "decision": "pass"} for i in range(3)]
    assert [c.index for _, c in join(events, calls)] == [0, 2, 4]


def _fx_shell(output: str) -> str:
    return json.dumps({"state": "completed", "exit_code": 0, "output_delta": output}, separators=(",", ":"))


def test_delivery_looks_inside_fx_framing():
    assert delivered("empty", _fx_shell(""), "", None)
    assert not delivered("empty", _fx_shell("x" * 400), "", None)
    stale = [("rate = 1.0", "rate = 1.1")]
    assert delivered("poison", _fx_shell("a\nrate = 1.1 tok\n"), "", "tok", stale)
    assert delivered("poison", _fx_shell("a\n"), "", "tok", stale) is None
    assert delivered("poison", _fx_shell("rate = 1.0\n"), "", "tok", stale) is False
    read = "<path>a.py</path>\n<content>\n1 \trate = 1.0\n</content>"
    assert delivered("poison", read, "", "tok", stale) is False


def test_join_maps_codex_exec_command_to_bash_records():
    calls = [Call(0, 0, 0, "exec_command", {"cmd": "ls"}, ""), Call(1, 1, 1, "apply_patch", {}, "")]
    events = [{"seq": 0, "tool_name": "Bash"}, {"seq": 1, "tool_name": "apply_patch"}]
    assert [c.index for _, c in join(events, calls)] == [0, 1]
    assert calls[0].command == "ls"


# Hashes produced by packages/fault-engine (`shortHash(canonicalArgs(...))`).
ENGINE_HASHES = [
    ("shell", {"command": "  git   log\n --oneline -3 "}, "b4acdf0d583d3bb4"),
    ("shell", {"command": 'echo "ñandú" | wc -c', "description": "x"}, "1838dad415a9b136"),
    ("mcp.tickets", {"query": "status:open", "limit": 5, "filters": {"b": [1, 2], "a": "z"}}, "9b755cc6d8fd79b3"),
    ("mcp.tickets", {"id": "T-12", "note": "café, línea\nsegunda"}, "c28e62bf64e9422c"),
]


@pytest.mark.parametrize(("capability", "args", "expected"), ENGINE_HASHES)
def test_args_hash_matches_the_engine(capability, args, expected):
    assert args_hash(capability, args) == expected


def test_args_hash_reads_codex_cmd_and_skips_path_capabilities():
    assert args_hash("shell", {"cmd": "git log --oneline -3"}) == "b4acdf0d583d3bb4"
    assert args_hash("fs.read", {"path": "a.py"}) is None
    assert args_hash("shell", {}) is None


def test_join_pairs_parallel_calls_by_args_hash():
    cmds = ["sleep 2; ls", "cat a", "cat b"]
    calls = [Call(i, i, i, "exec_command", {"cmd": c}, "") for i, c in enumerate(cmds)]
    # Logged in completion order, not trajectory order.
    events = [{"seq": i, "tool_name": "Bash", "capability": "shell", "args_hash": args_hash("shell", {"command": c})}
              for i, c in enumerate(["cat b", "sleep 2; ls", "cat a"])]
    assert [c.index for _, c in join(events, calls)] == [2, 0, 1]


def test_join_falls_back_to_position_without_a_matching_hash():
    calls = [Call(i, i, i, "Bash", {"command": c}, "") for i, c in enumerate(["a", "b", "c"])]
    events = [
        {"seq": 0, "tool_name": "Bash", "capability": "shell", "args_hash": args_hash("shell", {"command": "c"})},
        {"seq": 1, "tool_name": "Bash", "capability": "shell"},
        {"seq": 2, "tool_name": "Bash", "capability": "shell", "args_hash": "0000000000000000"},
        {"seq": 3, "tool_name": "Bash", "capability": "shell"},
    ]
    assert [c.index if c else None for _, c in join(events, calls)] == [2, 0, 1, None]
