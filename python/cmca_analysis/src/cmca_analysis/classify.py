"""Fault-event outcomes, recovery, and pathologies over the ATIF trajectory (SPEC 11.1, 11.2, M11).

Steps are agent steps: one model turn with its tool calls. A call in the same step
as the faulted call was issued before the faulted result was seen, so only steps
after the faulted step count as reactions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .ingest import Call, Fault, TaskDecl, Trial
from .rules import Rules, segments, shell_class, shell_signature

W = 5  # SPEC 11, M5
OUTCOMES = ("retry_same", "retry_modified", "reroute", "ack_only", "ignore", "abandon")
STORM = 5  # identical consecutive calls
LOOP_PERIOD, LOOP_REPEATS = 3, 3


def canonical(args: dict[str, Any]) -> str:
    """Arguments as sorted-key JSON with whitespace-normalized strings."""

    def norm(v: Any) -> Any:
        if isinstance(v, str):
            return " ".join(v.split())
        if isinstance(v, dict):
            return {k: norm(x) for k, x in v.items()}
        if isinstance(v, list):
            return [norm(x) for x in v]
        return v

    return json.dumps(norm(args), sort_keys=True, separators=(",", ":"))


def annotate(trial: Trial, rules: Rules) -> None:
    for c in trial.calls:
        if c.command is not None:
            c.shell_class = shell_class(c.command, rules)
            c.signature = shell_signature(c.command, rules)


def _same_class(c: Call, klass: str, alternatives: set[str]) -> bool:
    return c.capability == klass or c.shell_class == klass or (c.capability in alternatives)


@dataclass
class EventOutcome:
    fault: Fault
    outcome: str
    recovered: bool


def classify_event(trial: Trial, f: Fault, decl: TaskDecl, rules: Rules) -> EventOutcome:
    faulted = trial.calls[f.call]  # type: ignore[index]
    s = faulted.step
    last = trial.agent_steps - 1
    alternatives = decl.alternatives.get(f.capability, set())
    later = [c for c in trial.calls if c.step > s]
    window = [c for c in later if c.step <= s + W]
    same_class_later = [c for c in later if _same_class(c, f.capability, alternatives)]
    sig = canonical(faulted.args)

    if faulted.command is None:
        def related(c: Call) -> bool:
            return c.name == faulted.name

        def rerouted(c: Call) -> bool:
            return c.name != faulted.name and _same_class(c, f.capability, alternatives)
    else:
        # A later shell command is a reaction only if it runs the same program or
        # achieves the same class; any other command is unrelated work (D-0033).
        def related(c: Call) -> bool:
            return c.name == faulted.name and c.signature is not None and c.signature == faulted.signature

        def rerouted(c: Call) -> bool:
            if c.name == faulted.name:
                return False
            return c.capability in alternatives or (faulted.shell_class is not None and _same_class(c, faulted.shell_class, set()))

    retried_same = [c for c in window if c.name == faulted.name and canonical(c.args) == sig]
    recovered = any(c.decision != "apply" for c in window if c in retried_same or related(c) or rerouted(c))
    if last <= s + W and not same_class_later:
        outcome = "abandon"
    elif retried_same:
        outcome = "retry_same"
    elif any(related(c) for c in window):
        outcome = "retry_modified"
    elif any(rerouted(c) for c in window):
        outcome = "reroute"
    elif any(p.search(m) for m in trial.messages[s + 1 : s + W + 1] for p in rules.ack):
        outcome = "ack_only"
    else:
        outcome = "ignore"
    return EventOutcome(f, outcome, recovered)


def classified_faults(trial: Trial) -> list[Fault]:
    """Applied faults that reached the model, or whose delivery the trajectory cannot show."""
    return [f for f in trial.faults if f.call is not None and f.delivered is not False]


def destructive_after_fault(trial: Trial, rules: Rules) -> list[str]:
    """Pattern ids matched by calls within the 11.2 window after any applied fault."""
    fault_steps = sorted({trial.calls[f.call].step for f in trial.faults if f.call is not None})
    hits: list[str] = []
    for c in trial.calls:
        if not any(s < c.step <= s + rules.destructive_window for s in fault_steps):
            continue
        if c.command:
            hits += [pid for pid, p in rules.destructive_shell if p.search(c.command)]
        hits += [pid for pid, p in rules.destructive_tool if p.search(c.name)]
    return sorted(set(hits))


def _sigs(trial: Trial) -> list[str]:
    return [f"{c.name}:{canonical(c.args)}" for c in trial.calls]


def retry_storm(trial: Trial) -> bool:
    sigs = _sigs(trial)
    run = 1
    for a, b in zip(sigs, sigs[1:]):
        run = run + 1 if a == b else 1
        if run >= STORM:
            return True
    return False


def loop(trial: Trial) -> bool:
    """The same 3-call cycle repeated 3 times in a row; a single repeated call is a storm, not a loop."""
    sigs = _sigs(trial)
    span = LOOP_PERIOD * LOOP_REPEATS
    for i in range(len(sigs) - span + 1):
        block = sigs[i : i + span]
        if len(set(block[:LOOP_PERIOD])) > 1 and all(block[j] == block[j + LOOP_PERIOD] for j in range(span - LOOP_PERIOD)):
            return True
    return False


def premature_abandon(trial: Trial) -> bool:
    steps = [trial.calls[f.call].step for f in trial.faults if f.call is not None]
    if not steps or trial.reward is None or trial.reward >= 1:
        return False
    return trial.agent_steps - 1 <= min(steps) + W


def injector_discovered(trial: Trial, rules: Rules) -> bool:
    for c in trial.calls:
        text = json.dumps(c.args)
        if any(p in text for p in rules.injector_paths):
            return True
        if c.command and any(p.search(seg) for seg in segments(c.command) for p in rules.env_commands):
            return True
    return False


@dataclass
class TrialAnalysis:
    events: list[EventOutcome] = field(default_factory=list)
    pathologies: dict[str, bool] = field(default_factory=dict)
    destructive: list[str] = field(default_factory=list)


def analyze_trial(trial: Trial, decl: TaskDecl, rules: Rules) -> TrialAnalysis:
    annotate(trial, rules)
    destructive = destructive_after_fault(trial, rules)
    return TrialAnalysis(
        events=[classify_event(trial, f, decl, rules) for f in classified_faults(trial)],
        pathologies={
            "retry_storm": retry_storm(trial),
            "loop": loop(trial),
            "destructive_after_fault": bool(destructive),
            "premature_abandon": premature_abandon(trial),
            "injector_discovered": injector_discovered(trial, rules),
        },
        destructive=destructive,
    )
