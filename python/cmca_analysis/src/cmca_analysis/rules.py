"""Versioned rule files for classification (SPEC 11.1, 11.2, 7.8)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import yaml

RULES_DIR = Path(__file__).parent / "rules"


def _load(name: str) -> dict[str, Any]:
    return yaml.safe_load((RULES_DIR / name).read_text())


@dataclass(frozen=True)
class Rules:
    shell_classes: tuple[tuple[str, re.Pattern[str]], ...]
    ack: tuple[re.Pattern[str], ...]
    destructive_window: int
    destructive_shell: tuple[tuple[str, re.Pattern[str]], ...]
    destructive_tool: tuple[tuple[str, re.Pattern[str]], ...]
    injector_paths: tuple[str, ...]
    env_commands: tuple[re.Pattern[str], ...]
    track_exclusions: dict[str, dict[str, str]]
    track_exclusion_default: str
    versions: dict[str, int]


@cache
def load_rules() -> Rules:
    shell = _load("shell_class_map.yaml")
    ack = _load("errors_ack.yaml")
    destructive = _load("destructive_patterns.yaml")
    discovery = _load("discovery.yaml")
    exclusions = _load("track_exclusions.yaml")
    return Rules(
        shell_classes=tuple((cls, re.compile(p)) for cls, pats in shell["classes"].items() for p in pats),
        ack=tuple(re.compile(p, re.I) for p in ack["patterns"]),
        destructive_window=int(destructive["window_steps"]),
        destructive_shell=tuple((d["id"], re.compile(d["pattern"], re.I)) for d in destructive["shell"]),
        destructive_tool=tuple((d["id"], re.compile(d["pattern"], re.I)) for d in destructive["tool"]),
        injector_paths=tuple(discovery["injector_paths"]),
        env_commands=tuple(re.compile(p) for p in discovery["environment_commands"]),
        track_exclusions=exclusions["reasons"],
        track_exclusion_default=exclusions["default"],
        versions={
            "shell_class_map": shell["version"],
            "errors_ack": ack["version"],
            "destructive_patterns": destructive["version"],
            "discovery": discovery["version"],
        },
    )


_SEGMENT = re.compile(r"\|\||&&|[|;\n]")


def segments(command: str) -> list[str]:
    return [s for s in _SEGMENT.split(command) if s.strip()]


def shell_class(command: str, rules: Rules) -> str | None:
    """The built-in capability class a shell command achieves, or None."""
    for seg in segments(command):
        for cls, pat in rules.shell_classes:
            if pat.search(seg):
                return cls
    return None
