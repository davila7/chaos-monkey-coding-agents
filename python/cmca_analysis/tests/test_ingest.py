import tomllib

import pytest

from cmca_analysis.ingest import DATASETS, MCP_SERVERS, Call, bare_name, join


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
