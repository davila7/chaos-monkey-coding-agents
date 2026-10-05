import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

REMOTE_ROOT = "/opt/tt"
REMOTE_CONFIG = f"{REMOTE_ROOT}/config.json"
REMOTE_STATE = f"{REMOTE_ROOT}/state"
REMOTE_LOG_DIR = "/logs/agent/tt"
REMOTE_LOG = f"{REMOTE_LOG_DIR}/events.jsonl"


class TtOptions(BaseModel):
    """Options every CMCA agent declares so Harbor accepts them through `--ak`."""

    attempt_index: int | None = Field(default=None)
    # Host directory holding one resolved engine config per task, `<task>.json`,
    # written by `cmca plan`. Absent means the harness runs without the injector.
    tt_config_dir: str | None = Field(default=None)
    # Host directory with the built injector layout (`bin/`, plugin folders).
    tt_build_dir: str | None = Field(default=None)


def trial_task_name(logs_dir: Path) -> str:
    """Task directory name of the trial that owns `logs_dir` (`<trial>/agent`)."""
    trial_dir = logs_dir.parent
    config = trial_dir / "config.json"
    if config.exists():
        path = json.loads(config.read_text()).get("task", {}).get("path")
        if path:
            return Path(path).name
    return trial_dir.name.rsplit("__", 1)[0]


def engine_config(config_dir: Path, task: str, attempt: int, trial_id: str) -> dict[str, Any]:
    cfg = json.loads((config_dir / f"{task}.json").read_text())
    if cfg.get("schema") != "tt-engine/1":
        raise ValueError(f"{config_dir / f'{task}.json'}: not a tt-engine/1 config")
    if cfg.get("task_id") != task:
        raise ValueError(f"engine config task_id {cfg.get('task_id')!r} does not match task {task!r}")
    return {**cfg, "attempt": attempt, "trial_id": trial_id}


def read_events(logs_dir: Path) -> list[dict[str, Any]]:
    path = logs_dir / "tt" / "events.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
