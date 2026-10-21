import json
import tomllib

import pytest

from cmca_analysis.ingest import DATASETS, MCP_SERVERS, Call, bare_name, join
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
