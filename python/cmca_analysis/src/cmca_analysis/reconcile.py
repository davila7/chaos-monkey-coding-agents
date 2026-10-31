"""Reconciliation of applied faults with the trajectory (SPEC 9.5 reconciliation record)."""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Sequence

from .ingest import Trial, bare_name, content_text

TEXT_TYPES = {"deny", "err", "falsefail"}
_EMPTY_RENDERING = re.compile(r"\bempty\b|no (output|content)|without output", re.I)
# The status line Claude Code and Pi show for a failed shell command (V-01, V-10).
_EXIT_STATUS = re.compile(r"^(Exit code|Command exited with code) -?\d+$", re.M)
# fault-engine LINE_PREFIX: what `cat -n`, `grep -n` and `grep` over several files put before a line.
_LINE_PREFIX = re.compile(r"(\s*\d+\t|\d+[:-]|[^\t\n]*?:(\d+[:-])?)")


def shows_line(observation: str, line: str) -> bool:
    """Whether some output line is `line`, whole or after a prefix: the lines fault-engine replaceStaleLines rewrites."""
    for out in observation.split("\n"):
        out = out.removesuffix("\r")
        if out == line or (out.endswith(line) and _LINE_PREFIX.fullmatch(out[: len(out) - len(line)])):
            return True
    return False


_FX_READ = re.compile(r"^<path>.*?</path>\n<content>\n(.*)</content>$", re.S)
def fx_inner(observation: str) -> str:
    """The tool output inside fx's framing: file lines without numbers, or shell output; the input otherwise.

    fx 0.0.13 frames `read_file` output as `<path>..</path>` and numbered lines and
    `shell` output as a status JSON with the text in `output_delta` (V-27).
    """
    m = _FX_READ.match(observation)
    if m:
        return "".join(re.sub(r"^\d+ *\t", "", line) for line in m.group(1).splitlines(keepends=True))
    try:
        data = json.loads(observation)
    except ValueError:
        return observation
    if isinstance(data, dict) and isinstance(data.get("output_delta"), str):
        return data["output_delta"]
    return observation


# The header Codex 0.163.0 puts before a command, patch or MCP result (V-28):
# `Chunk ID`, `Wall time`, `Process exited with code` (or `Process running with
# session ID` for a command still running), `Original token count`
# or `Exit code` lines, then `Output:`.
_CODEX_FRAME = re.compile(r"^(?:(?:Chunk ID|Wall time|Process exited with code|Process running with session ID|Original token count|Exit code):? [^\n]*\n)+Output:(?:\n|$)")


def codex_inner(observation: str) -> str:
    """The tool output after Codex's header; the input otherwise."""
    return _CODEX_FRAME.sub("", observation, count=1)


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
    observation = fx_inner(codex_inner(observation))
    if fault_type == "empty":
        s = _EXIT_STATUS.sub("", mcp_text(observation)).strip()
        return s == "" or (len(s) < 300 and bool(_EMPTY_RENDERING.search(s)))
    if fault_type == "poison":
        if token and token in observation:
            return True
        # Shell poison replaces only the declared lines the output shows (D-0037), so a
        # matching command whose output shows none of them had nothing to deliver. Output
        # that reshapes a line (`cat -A`, a quoted repr) does not show it.
        if stale and not any(shows_line(observation, original) for original, _ in stale):
            return None
        return False
    # trunc needs the untruncated output to compare against, which is not logged; drift
    # and rate change structure or timing, which the observation text does not show.
    return None


def attribution_visible(fault_type: str, observation: str, payload: str) -> bool | None:
    """Whether the harness wrapped a delivered text payload in text of its own (SPEC 7.2)."""
    if fault_type not in TEXT_TYPES or not payload:
        return None
    text = mcp_text(codex_inner(observation))
    if payload not in text:
        return None
    return text.strip() != payload.strip()


def reconcile(trial: Trial, payloads: dict[str, str], token: str | None, stale: Sequence[tuple[str, str]] = ()) -> None:
    # Fewer trajectory calls than fault-log records for a tool means the harness left calls
    # out of its trajectory, so order no longer pairs records with calls for that tool.
    logged = Counter(bare_name(e.get("tool_name") or "") for e in trial.events)
    recorded = Counter(c.name for c in trial.calls)
    unpaired = {name for name, n in logged.items() if n > recorded[name]}
    taken = {f.call for f in trial.faults if f.call is not None}
    for f in trial.faults:
        if f.call is None:
            continue
        call = trial.calls[f.call]
        payload = payloads.get(f.payload_id or "", "")
        if call.name in unpaired:
            f.delivered = None
            f.attribution_visible = None
            continue
        f.delivered = delivered(f.type, call.observation, payload, token, stale)
        if f.delivered is False:
            # Calls issued in one step can reach the injector in either order, so the
            # fault may belong to another call of the same tool in that step.
            for c in trial.calls:
                if (
                    c.index not in taken and c.step == call.step and c.name == call.name
                    and delivered(f.type, c.observation, payload, token, stale)
                ):
                    taken.discard(f.call)
                    taken.add(c.index)
                    f.call, f.step_id, call, f.delivered = c.index, c.step_id, c, True
                    break
        f.attribution_visible = attribution_visible(f.type, call.observation, payload) if f.delivered else None
