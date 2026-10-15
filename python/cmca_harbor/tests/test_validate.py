import json
from pathlib import Path

from cmca_harbor import validate
from cmca_harbor.common import REPO_ROOT


def test_track_s_runs_oracle_under_every_profile_and_nop_clean(tmp_path: Path):
    runs = validate.commands(REPO_ROOT / "datasets/cmca-s", ["s-followups"], tmp_path, Path("jobs"))
    names = [r[r.index("--job-name") + 1] for r in runs]
    assert names == ["oracle-clean-a0", "oracle-light-a0", "oracle-moderate-a0", "oracle-heavy-a0", "nop-clean-a0"]
    assert all(r[-2:] == ["-i", "s-followups"] for r in runs)
    assert (tmp_path / "configs/oracle/heavy/s-followups.json").exists()


def test_config_dir_is_absolute(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runs = validate.commands(REPO_ROOT / "datasets/cmca-s", ["s-followups"], Path("out"), Path("jobs"))
    config_dir = next(a for a in runs[0] if a.startswith("TT_CONFIG_DIR=")).split("=", 1)[1]
    assert config_dir == str(tmp_path / "out/configs/oracle/clean")
    assert runs[0][runs[0].index("-o") + 1] == str(tmp_path / "jobs")


def test_track_n_runs_plain_oracle_and_nop(tmp_path: Path):
    runs = validate.commands(REPO_ROOT / "datasets/cmca-n", ["n-ledger-fix", "n-port-conflict"], tmp_path, Path("jobs"))
    assert [r[r.index("-a") + 1] for r in runs] == ["oracle", "nop"]
    assert all(r[-4:] == ["-i", "n-ledger-fix", "-i", "n-port-conflict"] for r in runs)


def _trial(jobs: Path, job: str, task: str, reward: float | None, events: list[dict] | None = None):
    trial = jobs / job / f"{task}__abc"
    trial.mkdir(parents=True)
    (trial / "config.json").write_text(json.dumps({"task": {"path": f"datasets/cmca-s/{task}/"}}))
    result = {"verifier_result": {"rewards": {"reward": reward}} if reward is not None else None, "exception_info": None}
    (trial / "result.json").write_text(json.dumps(result))
    if events:
        (trial / "agent/tt").mkdir(parents=True)
        (trial / "agent/tt/events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))


def test_collect_and_failures(tmp_path: Path):
    events = [{"decision": "apply", "type": "error"}, {"decision": "pass"}, {"decision": "ineligible"}]
    _trial(tmp_path, "oracle-moderate-a0", "s-a", 1.0, events)
    _trial(tmp_path, "nop-clean-a0", "s-a", 1.0)
    _trial(tmp_path, "oracle-moderate-a0", "s-b", None)
    jobs = ["oracle-moderate-a0", "nop-clean-a0"]
    rows = validate.collect(tmp_path, jobs)
    first = next(r for r in rows if r["job"] == "oracle-moderate-a0" and r["task"] == "s-a")
    assert (first["calls"], first["eligible"], first["applied"]) == (3, 2, {"error": 1})
    assert validate.failures(rows, ["s-a", "s-b"], jobs) == [
        "nop-clean-a0/s-b: no trial",
        "nop-clean-a0/s-a: reward 1.0, expected 0.0",
        "oracle-moderate-a0/s-b: reward None, expected 1.0",
    ]
