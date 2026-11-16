"""Stream names and active logs (docs/data.md, sections 3 and 4)."""

import re
from pathlib import Path

NAME = re.compile(r"[a-z][a-z0-9_-]*\Z")


def valid(name: str) -> bool:
    return bool(NAME.match(name))


def logs_dir(data: Path) -> Path:
    return data / "logs"


def log_path(data: Path, name: str) -> Path:
    return logs_dir(data) / f"{name}.log"


def active(data: Path) -> list[str]:
    """Names of the streams that have an active log, in name order."""
    d = logs_dir(data)
    if not d.is_dir():
        return []
    out = []
    for p in d.iterdir():
        if p.is_file() and p.name.endswith(".log") and valid(p.name[:-4]):
            out.append(p.name[:-4])
    return sorted(out)
