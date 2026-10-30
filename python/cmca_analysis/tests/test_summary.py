import json
from pathlib import Path

from cmca_analysis.trials import delivered, dumps, join_events, poison_eligible, summarize
from cmca_analysis.ingest import Fault, stale_lines
from cmca_analysis.reconcile import reconcile
from factory import call, trial

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
    assert clean["below_exposure_floor"] == 2 and clean["exposure"] == {"fs.read": 4, "shell": 2}
    assert clean["poison_eligible"] == 1 and moderate["poison_eligible"] == 1
    assert [t["poison_eligible"] for t in s["trials"]] == [None, True, None, None, True]
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
    assert delivered("empty", "Exit code 3", "", None) is True
    assert delivered("empty", "(no output)\n\nCommand exited with code 3", "", None) is True
    assert delivered("empty", "Exit code 3\n1\tline", "", None) is False
    assert delivered("poison", f"x {TOKEN}", "", TOKEN) is True
    assert delivered("trunc", "anything", "", None) is None


def test_shell_poison_delivery_counts_only_output_that_shows_the_lines():
    stale = [("rates use the month-end close", f"rates use {TOKEN}")]
    assert delivered("poison", f"12: rates use {TOKEN}", "", TOKEN, stale) is True
    assert delivered("poison", "12:rates use the month-end close", "", TOKEN, stale) is False
    assert delivered("poison", "    12\trates use the month-end close", "", TOKEN, stale) is False
    # The engine leaves reshaped lines alone, so they show nothing to replace.
    assert delivered("poison", "rates use the month-end close$", "", TOKEN, stale) is None
    assert delivered("poison", "'rates use the month-end close'", "", TOKEN, stale) is None
    assert delivered("poison", "Ran 755 tests\nOK", "", TOKEN, stale) is None
    assert delivered("poison", "Ran 755 tests\nOK", "", TOKEN) is False


def test_reconcile_pairs_a_fault_within_its_step_by_what_was_delivered():
    payloads = {"err.spawn": "Error: spawn /bin/sh EAGAIN"}
    calls = [call(0, 3, "bash", obs="47 /tmp/res\n"), call(1, 3, "bash", obs="Error: spawn /bin/sh EAGAIN"), call(2, 4, "bash", obs="ok")]
    f = Fault(seq=0, type="err", capability="shell", payload_id="err.spawn", persistence="transient", call=0)
    t = trial(calls=calls, faults=[f])
    t.events = [_event(i, "bash", "shell") for i in range(3)]
    reconcile(t, payloads, None)
    assert (f.call, f.delivered) == (1, True)


def test_reconcile_leaves_delivery_open_when_the_trajectory_lacks_calls():
    f = Fault(seq=1, type="deny", capability="mcp.x", payload_id="deny.x", persistence="sticky", call=0)
    t = trial(calls=[call(0, 0, "get_item", obs="{}")], faults=[f])
    t.events = [_event(0, "get_item", "mcp.x"), _event(1, "get_item", "mcp.x", "apply", "deny", "deny.x")]
    reconcile(t, {"deny.x": "Forbidden"}, None)
    assert f.delivered is None


def test_stale_lines_matches_the_engine():
    assert stale_lines("a\nb\n\nc", "a\nB\nx\nc") == [("b", "B")]
    assert stale_lines("a\nb", "a") == []


def test_poison_eligible_needs_an_eligible_matching_call():
    decl = [{"tool": "fs.read", "match": {"file_path": "/app/a.conf"}}]
    read = _event(0, "Read", "fs.read")
    assert poison_eligible([(read, ("Read", "", {"file_path": "/app/a.conf"}))], decl) is True
    assert poison_eligible([(read, ("Read", "", {"file_path": "/app/b.conf"}))], decl) is False
    assert poison_eligible([(_event(0, "Read", "fs.read", "skip"), ("Read", "", {"file_path": "/app/a.conf"}))], decl) is False
    assert poison_eligible([(_event(0, "Bash", "shell"), ("Bash", "", {"command": "cat /app/a.conf"}))], decl) is False


def test_track_s_reads_the_gateway_log_and_the_job_profile(tmp_path: Path):
    ev = tmp_path / "evidence"
    raw_empty = json.dumps({"server": "tickets", "tool": "mcp_tickets_get_ticket", "result": {"content": [{"type": "text", "text": ""}]}})
    raw_err = json.dumps({"result": {"content": [{"type": "text", "text": "Error: 503 Service Unavailable: upstream connect error or disconnect/reset before headers"}], "isError": True}})
    _trial(ev, "fx-claude-moderate-a0", "s1__x", "s1", "moderate", 0,
           [("mcp_tickets_get_ticket", raw_empty), ("mcp_tickets_search_tickets", raw_err)], [], 1.0, 0.1, "success")
    _trial(ev, "cc-claude-moderate-a0", "s1__y", "s1", "moderate", 0,
           [("mcp__tickets__get_ticket", "x"), ("mcp__tickets__get_ticket", "(mcp__tickets__get_ticket completed with no output)")], [], 1.0, 0.1, "success")
    gateway = {
        "s1__x": [_event(0, "get_ticket", "mcp.tickets.get_ticket", "apply", "empty", "empty.blank"),
                  _event(1, "search_tickets", "mcp.tickets.search_tickets", "apply", "err", "err.unavailable")],
        "s1__y": [_event(0, "get_ticket", "mcp.tickets.get_ticket"), _event(1, "get_ticket", "mcp.tickets.get_ticket", "apply", "empty", "empty.blank")],
    }
    for job, name in (("fx-claude-moderate-a0", "s1__x"), ("cc-claude-moderate-a0", "s1__y")):
        t = ev / job / name
        (t / "agent/tt/events.jsonl").unlink()
        (t / "agent/tt").rmdir()
        cfg = json.loads((t / "config.json").read_text())
        cfg["agent"]["kwargs"].pop("tt_config_dir")
        (t / "config.json").write_text(json.dumps(cfg))
        (t / "artifacts/var/log/tt").mkdir(parents=True)
        (t / "artifacts/var/log/tt/events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in gateway[name]))
    s = summarize(ev)
    assert list(s["profiles"]) == ["moderate"]
    m = s["profiles"]["moderate"]
    assert m["faults_unjoined"] == 0 and m["faults_by_type"] == {"empty": 2, "err": 1}
    assert (m["delivered"], m["delivery_verifiable"]) == (3, 3)


def test_codex_exec_command_joins_bash_records_and_its_header_is_read_past():
    obs = "Chunk ID: 6cb903\nWall time: 0.0000 seconds\nProcess exited with code 0\nOriginal token count: 0\nOutput:\n"
    joined = join_events([_event(0, "Bash", "shell")], [("exec_command", obs, {"cmd": "ls"})])
    assert joined[0][1] == obs
    assert delivered("empty", obs, "", None)
    assert delivered("empty", "Wall time: 0.0096 seconds\nOutput:", "", None)
    assert not delivered("empty", 'Wall time: 0.02 seconds\nOutput:\n{"id": 1}', "", None)
