"""Versioned rule files for classification (SPEC 11.1, 11.2, 7.8)."""

from __future__ import annotations

import re
import shlex
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
    program_skip: tuple[re.Pattern[str], ...]
    program_wrappers: tuple[tuple[str, ...], ...]
    program_interpreters: frozenset[str]
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
        program_skip=tuple(re.compile(p) for p in shell["program"]["skip_segments"]),
        program_wrappers=tuple(tuple(w.split()) for w in shell["program"]["wrappers"]),
        program_interpreters=frozenset(shell["program"]["interpreters"]),
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


_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_WRAPPER_ARG = re.compile(r"^(-.*|\d+(\.\d+)?[smhd]?|[A-Za-z_][A-Za-z0-9_]*=.*)$")


def _tokens(segment: str) -> list[str]:
    try:
        return shlex.split(segment)
    except ValueError:
        return segment.split()


_HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n.*?\n\s*\2\s*(?=\n|$)", re.S)


def _strip_heredocs(command: str) -> str:
    return _HEREDOC.sub(lambda m: m.group(0).split("\n", 1)[0], command)


def _lead_segment(command: str, rules: Rules) -> str | None:
    """The first segment that does work: heredoc bodies removed, directory and environment setup skipped."""
    for seg in segments(_strip_heredocs(command)):
        if not any(p.search(seg) for p in rules.program_skip):
            return seg
    return None


def shell_program(command: str, rules: Rules) -> str | None:
    """The program the command's lead segment runs (SPEC 11.1 rule 3, D-0033), or None."""
    seg = _lead_segment(command, rules)
    if seg is None:
        return None
    toks = _tokens(seg)
    while toks:
        if _ASSIGN.match(toks[0]):
            toks = toks[1:]
            continue
        w = next((w for w in rules.program_wrappers if tuple(toks[: len(w)]) == w), None)
        if w is None:
            break
        toks = toks[len(w) :]
        while toks and _WRAPPER_ARG.match(toks[0]):
            toks = toks[1:]
    if not toks:
        return None
    prog = toks[0].rsplit("/", 1)[-1]
    if prog not in rules.program_interpreters:
        return prog
    rest = toks[1:]
    while rest and rest[0].startswith("-") and rest[0] not in ("-m", "-c", "-"):
        rest = rest[1:]
    if not rest:
        return prog
    if rest[0] == "-m" and len(rest) > 1:
        return f"{prog} -m {rest[1]}"
    if rest[0] == "-c":
        return f"{prog} -c"
    if rest[0] == "-" or rest[0].startswith("<"):
        return f"{prog} -"  # script on stdin
    return f"{prog} {rest[0]}"


def shell_signature(command: str, rules: Rules) -> str | None:
    """What a shell command does, for rule 3: the class its lead segment achieves, else its program."""
    seg = _lead_segment(command, rules)
    if seg is None:
        return None
    for cls, pat in rules.shell_classes:
        if pat.search(seg):
            return cls
    return shell_program(command, rules)
