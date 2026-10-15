import json
from pathlib import Path

import pytest

from cmca_harbor import trials
from cmca_harbor.common import REPO_ROOT

DATASET = REPO_ROOT / "datasets/cmca-n"


def test_plan_writes_one_config_per_profile_and_task(tmp_path: Path):
    cmds = trials.plan("cc-claude", "s1", DATASET, ["clean", "moderate"], 2, tmp_path / "build", tmp_path / "out", Path("jobs"))
    names = [c[c.index("--job-name") + 1] for c in cmds]
    assert names == ["cc-claude-clean-a0", "cc-claude-clean-a1", "cc-claude-moderate-a0", "cc-claude-moderate-a1"]
    assert all("cmca_harbor:ChaosClaudeCode" in c and "claude-sonnet-5-5" in c for c in cmds)
    tasks = sorted(p.name for p in DATASET.iterdir() if (p / "task.toml").exists())
    for profile in ("clean", "moderate"):
        assert sorted(p.stem for p in (tmp_path / "out" / profile).iterdir()) == tasks
    cfg = json.loads((tmp_path / "out/moderate/n-port-conflict.json").read_text())
    caps = json.loads((REPO_ROOT / "capabilities/claude-code@2.1.289.json").read_text())
    assert cfg["parity_set"] == caps["parity_set"]
    assert {(g["type"], g["capability"]) for g in cfg["parity_gaps"]} == {("empty", "fs.write"), ("empty", "fs.edit")}
    assert cfg["task"]["poison"][0]["match"] == {"file_path": "/app/config/environments/prod-b.conf"}
    assert "rg-5d81f0" in cfg["variants"]["variants/prod-b.conf"]
    assert cfg["task"]["exposure"]["expected_classes"]
    clean = json.loads((tmp_path / "out/clean/n-port-conflict.json").read_text())
    assert clean["profile"]["base_rate"] == 0


def test_plan_refuses_unpinned_configs(tmp_path: Path):
    with pytest.raises(ValueError, match="pinned"):
        trials.plan("codex-gpt", "s1", DATASET, ["clean"], 1, tmp_path, tmp_path / "out", Path("jobs"))


def test_archive_copies_only_the_evidence(tmp_path: Path):
    t = tmp_path / "jobs/cc-claude-clean-a0/n-ledger-fix__a"
    (t / "agent/tt").mkdir(parents=True)
    (t / "verifier").mkdir()
    (t / "agent/sessions").mkdir()
    for rel in ("config.json", "result.json", "agent/trajectory.json", "agent/tt/events.jsonl", "verifier/reward.txt", "agent/sessions/raw.jsonl"):
        (t / rel).write_text("{}")
    (tmp_path / "jobs/conf-x").mkdir()
    assert trials.archive("cc-claude", tmp_path / "jobs", tmp_path / "out") == 5
    assert not (tmp_path / "out/cc-claude-clean-a0/n-ledger-fix__a/agent/sessions").exists()


def test_track_s_plan_uses_the_gateway_and_no_injector(tmp_path: Path):
    dataset = REPO_ROOT / "datasets/cmca-s"
    cmds = trials.plan("oracle", "s1", dataset, ["moderate"], 2, None, tmp_path / "out", Path("jobs"), track="s")
    assert [c[:3] for c in cmds] == [
        ["env", f"TT_CONFIG_DIR={tmp_path / 'out/moderate'}", "TT_ATTEMPT=0"],
        ["env", f"TT_CONFIG_DIR={tmp_path / 'out/moderate'}", "TT_ATTEMPT=1"],
    ]
    assert not any(a.startswith("tt_") for c in cmds for a in c)
    assert "-m" not in cmds[0]
    cfg = json.loads((tmp_path / "out/moderate/s-followups.json").read_text())
    assert cfg["layer"] == "service"
    assert cfg["parity_set"] == trials.TRACK_S_PARITY
    assert cfg["task"]["non_idempotent"] == [{"tool": "mcp.tickets.create_ticket"}, {"tool": "mcp.tickets.add_comment"}]
    assert cfg["task"]["drift"] == [{"tool": "mcp.tickets.search_tickets", "kind": "wrap", "under": "data"}]
    assert "r-7731" in cfg["variants"]["variants/ticket.json"]


def test_track_n_refuses_builtin_agents(tmp_path: Path):
    with pytest.raises(ValueError, match="Track N"):
        trials.plan("oracle", "s1", DATASET, ["clean"], 1, None, tmp_path / "out", Path("jobs"))
