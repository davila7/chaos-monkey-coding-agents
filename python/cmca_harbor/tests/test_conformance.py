import base64
import json
from pathlib import Path

import jsonschema
import pytest

from cmca_harbor import conformance as conf
from cmca_harbor.common import RESOLVED_SCHEMA_PATH, REPO_ROOT
from cmca_harbor.probes import ALL_PROBES, HEAD, POISON_TOKEN, TAIL, task_files


def test_committed_probe_tasks_match_the_generator():
    for probe in ALL_PROBES:
        task_dir = REPO_ROOT / "datasets/conformance" / probe.task
        for rel, content in task_files(REPO_ROOT, probe).items():
            assert (task_dir / rel).read_text() == content, f"{probe.task}/{rel}: run `python -m cmca_harbor.conformance tasks`"


def test_cells_follow_the_catalog():
    cells = conf.cells()
    assert ("falsefail", "fs.write") in cells and ("falsefail", "shell") not in cells
    assert ("poison", "fs.read") in cells and ("trunc", "fs.write") not in cells
    assert len(cells) == len(set(cells))


@pytest.mark.parametrize("cell", conf.cells())
def test_engine_configs_are_resolved(cell):
    cfg = conf.engine_config("pi", "1.0.3", *cell)
    jsonschema.validate(cfg, json.loads(RESOLVED_SCHEMA_PATH.read_text()))
    assert cfg["profile"]["class_rate_multipliers"][cell[1]] == 1
    assert sum(cfg["profile"]["class_rate_multipliers"].values()) == 1


def test_poison_configs_carry_the_variant():
    cfg = conf.engine_config("pi", "1.0.3", "poison", "fs.read")
    [decl] = cfg["task"]["poison"]
    assert POISON_TOKEN in cfg["variants"][decl["variant"]]


def test_plan_skips_classes_without_a_tool_and_adds_the_crash_job(tmp_path: Path):
    build = tmp_path / "build"
    (build / "bin").mkdir(parents=True)
    (build / "bin/tt-decide.cjs").write_text("")
    (build / "cc/hooks").mkdir(parents=True)
    (build / "cc/hooks/register.js").write_text("export const register = () => {};\n")
    cmds = conf.plan("claude-code", "2.1.289", "m", build, tmp_path / "out", tmp_path / "jobs")
    joined = [" ".join(c) for c in cmds]
    assert not any("probe-fs-list" in c for c in joined)
    assert len(cmds) == len(conf.TYPES) * conf.RUNS + 1
    assert "throw" in (tmp_path / "out/broken/cc/hooks/register.js").read_text()
    assert (build / "cc/hooks/register.js").read_text().startswith("export")
    assert sorted(c.split("--job-name ")[1].split(" ")[0][:-3] for c in joined if "probe-shell-fail" in c) == sorted(
        f"conf-claude-code-{t}" for t in ("empty", "trunc", "poison") for _ in range(conf.RUNS)
    )
    cfg = json.loads((tmp_path / "out/configs/poison/probe-shell-fail.json").read_text())
    assert cfg["task_id"] == "probe-shell-fail" and cfg["task"]["poison"][0]["source"] == "/app/probe/notes.txt"


def test_plan_can_keep_only_some_probes(tmp_path: Path):
    build = tmp_path / "build"
    (build / "bin").mkdir(parents=True)
    (build / "pi").mkdir()
    (build / "pi/index.js").write_text("")
    cmds = conf.plan("pi", "1.0.3", "m", build, tmp_path / "out", tmp_path / "jobs", only={"probe-shell-fail"})
    assert len(cmds) == 3 * conf.RUNS
    assert all(c.count("-i") == 1 and c[c.index("-i") + 1] == "probe-shell-fail" for c in cmds)
    assert not (tmp_path / "out/broken").exists()


@pytest.mark.parametrize(
    ("fault_type", "text", "payload", "expected"),
    [
        ("err", "Error: EIO: i/o error, read", "EIO: i/o error, read", (True, True)),
        ("deny", "EACCES: permission denied", "EACCES: permission denied", (True, False)),
        ("deny", "file contents", "EACCES: permission denied", (False, False)),
        ("empty", "", "", (True, False)),
        ("empty", "<system-reminder>the file exists but is empty</system-reminder>", "", (True, True)),
        ("empty", "File created successfully at: /app/probe/answer.txt", "", (False, False)),
        ("empty", f"1: {HEAD}", "", (False, False)),
        ("empty", "Exit code 3", "", (True, False)),
        ("empty", "(no output)\n\nCommand exited with code 3", "", (True, True)),
        ("empty", f"Exit code 3\nFirst line: {HEAD}", "", (False, False)),
        ("trunc", f"First line: {HEAD}\nEntry", "", (True, False)),
        ("trunc", f"First line: {HEAD} ... {TAIL}", "", (False, False)),
        ("poison", f"see ticket {POISON_TOKEN}", "", (True, False)),
    ],
)
def test_delivery_predicates(fault_type, text, payload, expected):
    assert conf.delivered(fault_type, text, payload) == expected


def _trial(root: Path, name: str, task: str, tool: str, output: str, events: list[dict], state: dict | None) -> Path:
    t = root / name
    (t / "agent/tt").mkdir(parents=True)
    (t / "verifier").mkdir()
    (t / "config.json").write_text(json.dumps({"task": {"path": f"/x/{task}"}}))
    traj = {
        "steps": [
            {"step_id": 1, "source": "user", "message": "go"},
            {
                "step_id": 2,
                "source": "agent",
                "message": "",
                "tool_calls": [{"tool_call_id": "c1", "function_name": tool, "arguments": {}}],
                "observation": {"results": [{"source_call_id": "c1", "content": [{"type": "text", "text": output}]}]},
            },
        ]
    }
    (t / "agent/trajectory.json").write_text(json.dumps(traj))
    (t / "agent/tt/events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
    if state is not None:
        (t / "verifier/state.json").write_text(json.dumps(state))
    return t


def _event(fault_type: str, capability: str, payload_id: str, latency: float = 2.0) -> dict:
    return {"decision": "apply", "type": fault_type, "capability": capability, "payload_id": payload_id, "latency_ms": latency}


def test_check_trial_pre_phase_write(tmp_path: Path):
    t = _trial(tmp_path, "a", "probe-fs-write", "write", "Error: EACCES: permission denied",
               [_event("deny", "fs.write", "deny.eacces")], {"exists": False})
    r = conf.check_trial(t, "pi", "deny", "fs.write")
    assert r == r | {"exposed": True, "logged": True, "delivered": True, "attribution_visible": True, "side_effect": True, "passed": True}


def test_check_trial_fails_when_the_side_effect_is_wrong(tmp_path: Path):
    ok = {"exists": True, "content_b64": base64.b64encode(b"ready\n").decode()}
    t = _trial(tmp_path, "a", "probe-fs-write", "write", "Error: EACCES: permission denied",
               [_event("deny", "fs.write", "deny.eacces")], ok)
    assert conf.check_trial(t, "pi", "deny", "fs.write")["side_effect"] is False
    t2 = _trial(tmp_path, "b", "probe-fs-write", "write", "EIO: i/o error, write",
                [_event("falsefail", "fs.write", "falsefail.eio.write")], ok)
    assert conf.check_trial(t2, "pi", "falsefail", "fs.write")["passed"] is True


def test_check_trial_latency_and_exposure(tmp_path: Path):
    slow = _trial(tmp_path, "a", "probe-shell", "bash", "", [_event("empty", "shell", "empty.blank", 400)], {"exists": True})
    r = conf.check_trial(slow, "pi", "empty", "shell")
    assert r["delivered"] and not r["latency_ok"] and not r["passed"]
    unexposed = _trial(tmp_path, "b", "probe-fs-search", "bash", "x", [], None)
    assert conf.check_trial(unexposed, "pi", "deny", "fs.search")["exposed"] is False


def test_report_builds_the_parity_set_with_gaps(tmp_path: Path):
    jobs = tmp_path / "jobs"
    for a in range(conf.RUNS):
        d = jobs / f"conf-pi-empty-a{a}"
        _trial(d, "read", "probe-fs-read", "read", "", [_event("empty", "fs.read", "empty.blank")], None)
        _trial(d, "write", "probe-fs-write", "write", "Wrote file", [_event("empty", "fs.write", "empty.blank")],
               {"exists": True, "content_b64": base64.b64encode(b"ready").decode()})
        d = jobs / f"conf-pi-deny-a{a}"
        _trial(d, "read", "probe-fs-read", "read", "EACCES: permission denied", [_event("deny", "fs.read", "deny.eacces")], None)
        d = jobs / f"conf-pi-trunc-a{a}"
        _trial(d, "shell", "probe-shell", "bash", f"First line: {HEAD}", [_event("trunc", "shell", "trunc.head30")], {"exists": True})
        failed = f"First line: {HEAD}" if a < 2 else f"First line: {HEAD} {TAIL}"
        _trial(d, "shell-fail", "probe-shell-fail", "bash", failed + "\n\nCommand exited with code 3",
               [_event("trunc", "shell", "trunc.head30")], {"exists": True})
    crash = jobs / "conf-pi-crash-a0"
    _trial(crash, "shell", "probe-shell", "bash", f"First line: {HEAD}", [], {"exists": True})

    no_gap = conf.report("pi", "1.0.3", jobs, {})
    assert no_gap["faults"]["empty"]["supported"] is False
    assert no_gap["faults"]["empty"]["reason"] == "failing classes: fs.write"
    assert no_gap["parity_set"] == ["deny"]

    caps = conf.report("pi", "1.0.3", jobs, {("empty", "fs.write"): "mapper renders a fixed line"})
    assert caps["parity_set"] == ["deny", "empty"]
    assert caps["parity_gaps"] == [{"type": "empty", "capability": "fs.write", "reason": "mapper renders a fixed line"}]
    assert caps["faults"]["empty"]["runs_passed"] == 3
    assert caps["tool_map"] == {"bash": "shell", "read": "fs.read", "write": "fs.write"}
    assert caps["faults"]["trunc"]["classes"]["shell"] == caps["faults"]["trunc"]["classes"]["shell"] | {"runs": 6, "runs_passed": 5}
    assert caps["faults"]["trunc"]["supported"] is False
    assert caps["crash_behavior"] == "fail_open"
    assert caps["injector_p95_ms"] == 2.0


def test_archive_copies_only_the_evidence(tmp_path: Path):
    jobs = tmp_path / "jobs"
    t = _trial(jobs / "conf-pi-deny-a0", "read", "probe-fs-read", "read", "x", [_event("deny", "fs.read", "deny.eacces")], None)
    (t / "agent/sessions").mkdir()
    (t / "agent/sessions/raw.jsonl").write_text("{}")
    assert conf.archive(jobs, tmp_path / "out") == 3
    assert sorted(p.relative_to(tmp_path / "out").as_posix() for p in (tmp_path / "out").rglob("*") if p.is_file()) == [
        "conf-pi-deny-a0/read/agent/trajectory.json",
        "conf-pi-deny-a0/read/agent/tt/events.jsonl",
        "conf-pi-deny-a0/read/config.json",
    ]


def test_fx_inner_reads_inside_fx_framing():
    from cmca_harbor.conformance import fx_inner

    assert fx_inner("read_file", "<path>probe/notes.txt</path>\n<content>\n</content>") == ""
    assert fx_inner("read_file", "<path>a</path>\n<content>\n9 \tnine\n10\tten\n</content>") == "nine\nten\n"
    assert fx_inner("shell", json.dumps({"exit_code": 0, "output_delta": ""})) == ""
    assert fx_inner("grep_files", "") == ""
    assert fx_inner("shell", "not json") == "not json"


def test_codex_inner_reads_inside_codex_framing():
    from cmca_harbor.conformance import codex_inner

    shell = "Chunk ID: a1b2c3\nWall time: 0.0012 seconds\nProcess exited with code 3\nOriginal token count: 2\nOutput:\nline\n"
    assert codex_inner("exec_command", shell) == "line\n"
    assert codex_inner("exec_command", shell.replace("line\n", "")) == ""
    patch = "Exit code: 0\nWall time: 0 seconds\nOutput:\nSuccess. Updated the following files:\nM a.txt\n"
    assert codex_inner("apply_patch", patch) == "Success. Updated the following files:\nM a.txt\n"
    assert codex_inner("exec_command", "unframed") == "unframed"


def test_a_tool_can_serve_several_classes():
    from cmca_harbor.conformance import HARNESSES, class_calls, tool_classes

    tools = HARNESSES["codex"].tools
    assert tool_classes(tools) == {"shell", "fs.edit", "fs.write"}
    trajectory = {"steps": [{"tool_calls": [{"function_name": "apply_patch", "tool_call_id": "c1"}], "observation": {"results": [{"source_call_id": "c1", "content": "out"}]}}]}
    assert class_calls(trajectory, tools, "fs.write") == [("apply_patch", "out")]
    assert class_calls(trajectory, tools, "fs.edit") == [("apply_patch", "out")]
    assert class_calls(trajectory, tools, "shell") == []
