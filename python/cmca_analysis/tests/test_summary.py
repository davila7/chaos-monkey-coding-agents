import json
from pathlib import Path

from cmca_analysis.trials import delivered, dumps, join_events, summarize

SNAPSHOT = Path(__file__).parent / "snapshots/trials-summary.json"
TOKEN = "pmt-abc123"


def _event(seq, tool, capability, decision="pass", fault_type=None, payload_id=None):
    return {
        "schema": "tt-event/2",
        "seq": seq,
        "tool_name": tool,
        "capability": capability,
        "decision": decision,
        "type": fault_type,
        "payload_id": payload_id,
        "exempt_reason": "exempt_path" if decision == "skip" else None,
    }


def _trial(root: Path, job: str, name: str, task: str, profile: str, attempt: int, calls, events, reward, cost, status=None, extra=None):
    t = root / job / name
    (t / "agent/tt").mkdir(parents=True)
    (t / "verifier").mkdir()
    (t / "config.json").write_text(
        json.dumps({"task": {"path": f"/d/{task}"}, "agent": {"kwargs": {"tt_config_dir": f"/p/{profile}", "attempt_index": attempt}}})
    )
    result = {
        "verifier_result": None if reward is None else {"rewards": {"reward": reward}},
        "exception_info": {"exception_type": "AgentSetupTimeoutError"} if reward is None else None,
        "agent_result": {"cost_usd": cost, "n_input_tokens": 1000, "n_output_tokens": 100},
    }
    (t / "result.json").write_text(json.dumps(result))
    steps = [
        {
            "step_id": i + 2,
            "source": "agent",
            "tool_calls": [{"tool_call_id": f"c{i}", "function_name": tool}],
            "observation": {"results": [{"source_call_id": f"c{i}", "content": [{"type": "text", "text": obs}]}]},
        }
        for i, (tool, obs) in enumerate(calls)
    ]
    (t / "agent/trajectory.json").write_text(json.dumps({"steps": [{"step_id": 1, "source": "user"}, *steps]}))
    (t / "agent/tt/events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
    if status is not None:
        (t / "verifier/STATUS.json").write_text(json.dumps({"status": status, "summary": "x"}))
    for rel, text in (extra or {}).items():
        (t / "verifier" / rel).write_text(text)


def _fixture(root: Path) -> Path:
    ev = root / "evidence"
    reads = [("Read", "a"), ("Bash", "ok"), ("Read", "b")]
    _trial(ev, "cc-clean-a0", "t1__x", "t1", "clean", 0, reads,
           [_event(0, "Read", "fs.read"), _event(1, "Bash", "shell"), _event(2, "Read", "fs.read")], 1.0, 0.10, "success")
    _trial(ev, "cc-clean-a0", "t2__x", "t2", "clean", 0, reads,
           [_event(0, "Read", "fs.read"), _event(1, "Bash", "shell"), _event(2, "Read", "fs.read")], 0.0, 0.20, "partial")
    _trial(ev, "cc-moderate-a0", "t1__y", "t1", "moderate", 0,
           [("Read", "EACCES: permission denied"), ("Bash", "(Bash completed with no output)"), ("Read", "a")],
           [_event(0, "Read", "fs.read", "apply", "deny", "deny.eacces"), _event(1, "Bash", "shell", "apply", "empty", "empty.blank"),
            _event(2, "Read", "fs.read")], 0.0, 0.30, "success")
    _trial(ev, "cc-moderate-a0", "t2__y", "t2", "moderate", 0,
           [("Write", "File created"), ("Read", f"see {TOKEN}"), ("Read", "short")],
           [_event(0, "Write", "fs.write", "skip"), _event(1, "Read", "fs.read", "apply", "poison", "poison.variant"),
            _event(2, "Read", "fs.read", "apply", "trunc", "trunc.half")], 1.0, 0.40, "success", {"check.txt": f"owner {TOKEN}"})
    _trial(ev, "cc-moderate-a1", "t1__z", "t1", "moderate", 1, [], [], None, None)
    data = root / "dataset"
    for task in ("t1", "t2"):
        (data / task).mkdir(parents=True)
        poison = f'\n[[poison]]\ntool = "fs.read"\nvariant = "v"\ntoken = "{TOKEN}"\n' if task == "t2" else ""
        (data / task / "chaos.toml").write_text(f'schema = "tt-task/1"\n{poison}')
    return root


def test_summary_matches_the_snapshot(tmp_path: Path):
    root = _fixture(tmp_path)
    assert dumps(summarize(root / "evidence", root / "dataset")) == SNAPSHOT.read_text()


def test_summary_is_byte_identical_across_runs(tmp_path: Path):
    a = _fixture(tmp_path / "a")
    b = _fixture(tmp_path / "b")
    assert dumps(summarize(a / "evidence", a / "dataset")) == dumps(summarize(b / "evidence", b / "dataset"))


def test_summary_figures(tmp_path: Path):
    root = _fixture(tmp_path)
    s = summarize(root / "evidence", root / "dataset")
    clean, moderate = s["profiles"]["clean"], s["profiles"]["moderate"]
    assert clean["pass1"] == 0.5 and moderate["pass1"] == 0.5
    assert moderate["infra_failures"] == 1 and moderate["trials"] == 3
    assert moderate["faults_by_type"] == {"deny": 1, "empty": 1, "poison": 1, "trunc": 1}
    assert (moderate["delivered"], moderate["delivery_verifiable"]) == (3, 3)
    assert moderate["overclaim"] == {"faulted_failed": 1, "status_success": 1}
    assert moderate["poison_propagated"] == 1
    assert clean["eligible_calls_min"] == 3 and clean["cost_usd_total"] == 0.3
    assert s["retention"] == {"moderate": 1.0}


def test_join_follows_per_tool_order():
    events = [_event(1, "Read", "fs.read"), _event(0, "Bash", "shell"), _event(2, "Read", "fs.read", "apply", "deny")]
    joined = join_events(events, [("Bash", "b0"), ("Read", "r0"), ("Read", "r1")])
    assert [(e["seq"], obs) for e, obs in joined] == [(0, "b0"), (1, "r0"), (2, "r1")]
    assert join_events([_event(0, "Grep", "fs.search")], [])[0][1] is None


def test_delivery_predicates():
    assert delivered("deny", "Error: EACCES: permission denied", "EACCES: permission denied", None) is True
    assert delivered("deny", "file text", "EACCES: permission denied", None) is False
    assert delivered("empty", "", "", None) is True
    assert delivered("empty", "1\tline", "", None) is False
    assert delivered("poison", f"x {TOKEN}", "", TOKEN) is True
    assert delivered("trunc", "anything", "", None) is None
