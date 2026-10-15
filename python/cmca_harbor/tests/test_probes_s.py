import json

import pytest

from cmca_harbor import probes_s
from cmca_harbor.common import REPO_ROOT
from cmca_harbor.probes import HEAD, POISON_TOKEN, TAIL


def test_committed_probe_tasks_match_the_generator():
    for name in probes_s.PROBES:
        task_dir = probes_s.DATASET / name
        for rel, content in probes_s.task_files(REPO_ROOT, name).items():
            assert (task_dir / rel).read_text() == content, f"{name}/{rel}: run `python -m cmca_harbor.probes_s write`"


def test_every_service_type_is_probed_once():
    types = [t for p in probes_s.PROBES.values() for t in p["types"]]
    assert sorted(types) == sorted(["deny", "err", "empty", "trunc", "falsefail", "poison", "drift", "latency", "rate"])


@pytest.mark.parametrize("config", ["fx-claude", "cc-claude"])
def test_plan_writes_one_config_per_task_and_job(tmp_path, config):
    cmds = probes_s.plan(config, tmp_path / "cfg", tmp_path / "jobs")
    assert len(cmds) == 10
    clean = json.loads((tmp_path / "cfg/clean/probe-s-write.json").read_text())
    assert clean["profile"]["base_rate"] == 0 and clean["layer"] == "service"
    ff = json.loads((tmp_path / "cfg/falsefail/probe-s-write.json").read_text())
    assert ff["profile"]["weights"] == {"falsefail": 1}
    assert ff["task"]["non_idempotent"] == [{"tool": "mcp.tickets.add_comment"}]
    assert not (tmp_path / "cfg/falsefail/probe-s-read.json").exists()


def test_delivery_rules():
    body = f"First line: {HEAD}\\nEntry 01\\nLast line: {TAIL}"
    wrapped = json.dumps({"result": {"content": [{"type": "text", "text": json.dumps({"id": 501, "body": body})}]}})
    assert probes_s.delivered(None, wrapped, "")
    assert probes_s.delivered("err", json.dumps({"text": 'Error: "x"'}), 'Error: "x"')
    assert probes_s.delivered("trunc", f"First line: {HEAD}\nEntry", "")
    assert not probes_s.delivered("trunc", wrapped, "")
    assert probes_s.delivered("empty", "", "")
    assert probes_s.delivered("poison", f"see ticket {POISON_TOKEN}", "")
    assert probes_s.delivered("drift", json.dumps({"text": json.dumps({"id": 501, "description": "x"})}), "")
    assert not probes_s.delivered("drift", wrapped, "")


def test_write_probe_checks_the_comment_and_the_side_effect(tmp_path):
    trial = tmp_path / "probe-s-write__x"
    (trial / "agent").mkdir(parents=True)
    (trial / "verifier").mkdir()
    (trial / "artifacts/var/log/tt").mkdir(parents=True)
    (trial / "config.json").write_text(json.dumps({"task": {"path": "datasets/conformance-s/probe-s-write"}}))
    (trial / "verifier/reward.txt").write_text("1\n")
    (trial / "artifacts/var/log/tt/events.jsonl").write_text(json.dumps({"decision": "pass"}) + "\n")
    obs = json.dumps({"type": "text", "text": json.dumps({"ticket_id": 501, "comment_id": "c-1"})})
    step = {"source": "agent", "message": "done", "tool_calls": [{"tool_call_id": "1", "function_name": "mcp__tickets__add_comment"}],
            "observation": {"results": [{"source_call_id": "1", "content": obs}]}}
    (trial / "agent/trajectory.json").write_text(json.dumps({"steps": [step]}))
    one = {"tool": "add_comment", "replayed": False}
    (trial / "verifier/state.json").write_text(json.dumps({"mutations": [one]}))
    assert probes_s.check_trial(trial, None)["passed"]
    (trial / "verifier/state.json").write_text(json.dumps({"mutations": [one, one]}))
    assert not probes_s.check_trial(trial, None)["passed"]
