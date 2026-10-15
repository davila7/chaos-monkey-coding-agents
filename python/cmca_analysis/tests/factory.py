"""In-memory trial records for unit tests."""

from __future__ import annotations

from typing import Any

from cmca_analysis.ingest import Call, Fault, Trial


def call(i: int, step: int, tool: str, args: dict[str, Any] | None = None, obs: str = "", capability: str | None = None, decision: str | None = "pass") -> Call:
    return Call(index=i, step=step, step_id=step + 2, tool=tool, args=args or {}, observation=obs, capability=capability, decision=decision)


def fault(call_index: int | None, type_: str = "err", capability: str = "shell", delivered: bool | None = True) -> Fault:
    return Fault(seq=None, type=type_, capability=capability, payload_id=None, persistence="transient", call=call_index, delivered=delivered)


def trial(
    *,
    task: str = "t1",
    profile: str = "moderate",
    attempt: int = 0,
    reward: float | None = 1.0,
    status: str = "success",
    calls: list[Call] | None = None,
    faults: list[Fault] | None = None,
    messages: list[str] | None = None,
    steps: int | None = None,
    cost: float | None = 0.1,
    tokens: tuple[int, int] = (1000, 100),
    wall: float | None = 60.0,
    artifact_text: str = "",
    service_state: dict[str, Any] | None = None,
    name: str | None = None,
    exception_type: str | None = None,
) -> Trial:
    calls = calls or []
    n_steps = steps if steps is not None else (max((c.step for c in calls), default=-1) + 1)
    msgs = messages if messages is not None else [""] * n_steps
    return Trial(
        trial=name or f"{task}-{profile}-{attempt}",
        job=f"cfg-{profile}-a{attempt}",
        path=f"ev/cfg-{profile}-a{attempt}/{name or task}",
        config_id="cfg",
        track="n",
        task=task,
        profile=profile,
        attempt=attempt,
        reward=reward,
        infra_failure=exception_type if reward is None else None,
        exception_type=exception_type,
        cost_usd=cost,
        cost_source="result.json" if cost is not None else None,
        input_tokens=tokens[0],
        output_tokens=tokens[1],
        wall_seconds=wall,
        finished_at=None,
        status=status,
        agent_steps=n_steps,
        messages=msgs,
        calls=calls,
        events=[],
        faults=faults or [],
        artifact_text=artifact_text,
        verifier_text="",
        service_state=service_state,
        poison_eligible=None,
    )
