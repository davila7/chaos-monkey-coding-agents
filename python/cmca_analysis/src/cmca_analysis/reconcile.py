"""Reconciliation of applied faults with the trajectory (SPEC 9.5 reconciliation record)."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence

from .ingest import Trial, content_text

TEXT_TYPES = {"deny", "err", "falsefail"}
_EMPTY_RENDERING = re.compile(r"\bempty\b|no (output|content)|without output", re.I)


def mcp_text(observation: str) -> str:
    """The text content of an MCP result that fx passed on as raw JSON; the input otherwise."""
    try:
        data = json.loads(observation)
    except ValueError:
        return observation
    result = data.get("result") if isinstance(data, dict) else None
    if not isinstance(result, dict) or not isinstance(result.get("content"), list):
        return observation
    return content_text(result["content"])


def delivered(
    fault_type: str, observation: str, payload: str, token: str | None, stale: Sequence[tuple[str, str]] = ()
) -> bool | None:
    """Whether the payload reached the model; None where the trajectory alone cannot tell."""
    if fault_type in TEXT_TYPES:
        # fx passes the raw MCP result on, so the payload can arrive JSON-escaped.
        return bool(payload) and (payload in observation or json.dumps(payload)[1:-1] in observation)
    if fault_type == "empty":
        s = mcp_text(observation).strip()
        return s == "" or (len(s) < 300 and bool(_EMPTY_RENDERING.search(s)))
    if fault_type == "poison":
        if token and token in observation:
            return True
        # Shell poison replaces only the declared lines the output shows (D-0037), so a
        # matching command whose output shows none of them had nothing to deliver.
        if stale and not any(original in observation for original, _ in stale):
            return None
        return False
    # trunc needs the untruncated output to compare against, which is not logged; drift
    # and rate change structure or timing, which the observation text does not show.
    return None


def attribution_visible(fault_type: str, observation: str, payload: str) -> bool | None:
    """Whether the harness wrapped a delivered text payload in text of its own (SPEC 7.2)."""
    if fault_type not in TEXT_TYPES or not payload:
        return None
    text = mcp_text(observation)
    if payload not in text:
        return None
    return text.strip() != payload.strip()


def reconcile(trial: Trial, payloads: dict[str, str], token: str | None, stale: Sequence[tuple[str, str]] = ()) -> None:
    for f in trial.faults:
        if f.call is None:
            continue
        obs = trial.calls[f.call].observation
        payload = payloads.get(f.payload_id or "", "")
        f.delivered = delivered(f.type, obs, payload, token, stale)
        f.attribution_visible = attribution_visible(f.type, obs, payload) if f.delivered else None
