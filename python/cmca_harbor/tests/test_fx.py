import json
from pathlib import Path

from harbor.utils.trajectory_validator import validate_trajectory

from cmca_harbor.fx import ARCHIVES, session_to_atif

# A real fx 0.0.13 session (openai/gpt-5.4-nano on the free gateway tier, one
# MCP get_ticket call and one shell call), captured on 2026-10-15 for V-09.
SESSION = Path(__file__).parent / "data/fx-session-0.0.13"


def test_session_converts_to_valid_atif():
    traj = session_to_atif(SESSION, version="0.0.13", model="openai/gpt-5.4-nano")
    doc = traj.to_json_dict()
    assert validate_trajectory(doc)
    calls = [c for s in traj.steps for c in (s.tool_calls or [])]
    assert [c.function_name for c in calls] == [
        "mcp_select_tool", "mcp_features", "mcp_features", "capability_search", "mcp_tickets_get_ticket", "shell",
    ]
    ticket = next(c for c in calls if c.function_name == "mcp_tickets_get_ticket")
    assert ticket.arguments == {"id": 211}
    observed = {r.source_call_id: r for s in traj.steps if s.observation for r in s.observation.results}
    assert set(observed) == {c.tool_call_id for c in calls}
    # Full tool output comes from tool-results/, not the truncated preview.
    assert json.loads(observed[ticket.tool_call_id].content)["result"]["content"][0]["text"].startswith('{"id":211')
    assert traj.steps[0].source == "user"
    assert traj.final_metrics.total_prompt_tokens == 49052
    assert traj.final_metrics.total_cost_usd > 0


def test_every_pinned_version_has_both_archives():
    for sums in ARCHIVES.values():
        assert set(sums) == {"x86_64", "aarch64"}
        assert all(len(v) == 64 for v in sums.values())


def test_provider_is_pinned_from_the_model_id(tmp_path):
    from cmca_harbor.fx import ChaosFx

    env = ChaosFx(logs_dir=tmp_path, model_name="anthropic/claude-sonnet-5.5", version="0.0.13").resolve_env_vars()
    assert env["FX_PROVIDER_ORDER"] == "anthropic" and env["FX_PROVIDER_STRICT"] == "1"


def test_pending_generations_are_settled_or_cost_is_withheld(tmp_path):
    import shutil

    from cmca_harbor.fx import settle_usage

    # Shape of a real 2026-10-15 snapshot copied before fx's billing settled.
    snapshot = {"billing": "pending", "total_cost": 0.068602, "cache_read_tokens": 0, "pending": [{"id": "gen_a"}, {"id": "gen_b"}]}
    looked_up = {"gen_a": {"total_cost": 0.0053577, "native_tokens_cached": 14237}, "gen_b": {"total_cost": 0.01, "native_tokens_cached": 100}}
    settled = settle_usage(snapshot, looked_up.get)
    assert abs(settled["total_cost"] - 0.0839597) < 1e-9 and settled["cache_read_tokens"] == 14337
    assert settle_usage(snapshot, lambda _id: None) is None

    session = tmp_path / "s"
    shutil.copytree(SESSION, session)
    (session / "usage-v2.json").write_text(json.dumps({"snapshot": snapshot}))
    usage = {"input_tokens": 132978, "output_tokens": 2362}
    unsettled = session_to_atif(session, version="0.0.13", model="m", usage=usage).final_metrics
    assert unsettled.total_cost_usd is None and unsettled.total_prompt_tokens == 132978
    assert session_to_atif(session, version="0.0.13", model="m", usage=usage, settled=settled).final_metrics.total_cost_usd == settled["total_cost"]
