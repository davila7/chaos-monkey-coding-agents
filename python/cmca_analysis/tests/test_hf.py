import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
RELEASE = ROOT / "results" / "2026-10-31-m5-codex"
HF = RELEASE / "hf"


@pytest.mark.skipif(not HF.exists(), reason="committed hf tables not present")
def test_committed_tables_match_the_release():
    trials = [json.loads(line) for line in (HF / "trials.jsonl").read_text().splitlines()]
    tasks = [json.loads(line) for line in (HF / "tasks.jsonl").read_text().splitlines()]
    meta = json.loads((HF / "meta.json").read_text())
    assert meta["trials"] == len(trials) and meta["tasks"] == len(tasks)

    site = json.loads((RELEASE / "site-data.json").read_text())
    for board in site["boards"]:
        track = "s" if board["id"] == "track-s" else "n"
        for row in board["rows"]:
            mine = [t for t in trials if t["config_id"] == row["config_id"] and t["track"] == track and t["profile"] == "moderate" and not t["excluded"]]
            # Same counts the site shows: tasks completed under `moderate` out of valid trials sent.
            assert sum(t["success"] for t in mine) == row["faulted_counts"]["succeeded"], row["config_id"]
            assert len(mine) == row["faulted_counts"]["sent"], row["config_id"]

    assert {t["task_id"] for t in trials} == {t["task_id"] for t in tasks if t["in_release"]}
    assert all("canary GUID" not in t["instruction"] for t in tasks)
