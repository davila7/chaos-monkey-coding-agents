"""Ingest and validate injection records (SPEC 9.5, schema tt-event/2)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[4]
EVENT_SCHEMA_PATH = REPO_ROOT / "packages/fault-engine/schemas/tt-event-2.schema.json"


@cache
def _validator() -> Draft202012Validator:
    return Draft202012Validator(json.loads(EVENT_SCHEMA_PATH.read_text()))


@dataclass
class EventLogReport:
    records: list[dict[str, Any]]
    invalid: list[tuple[int, str]] = field(default_factory=list)
    missing_seq: list[int] = field(default_factory=list)
    duplicate_seq: list[int] = field(default_factory=list)
    error_records: int = 0

    @property
    def ok(self) -> bool:
        return not (self.invalid or self.missing_seq or self.duplicate_seq)


def sequence_problems(seqs: list[int]) -> tuple[list[int], list[int]]:
    """Missing and duplicated sequence numbers, assuming a trial starts at 0."""
    if not seqs:
        return [], []
    seen: set[int] = set()
    dups: set[int] = set()
    for s in seqs:
        (dups if s in seen else seen).add(s)
    missing = [s for s in range(max(seen) + 1) if s not in seen]
    return missing, sorted(dups)


def read_event_log(path: Path) -> EventLogReport:
    records: list[dict[str, Any]] = []
    invalid: list[tuple[int, str]] = []
    for lineno, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as e:
            invalid.append((lineno, f"json: {e.msg}"))
            continue
        errors = sorted(_validator().iter_errors(rec), key=lambda e: list(e.path))
        if errors:
            invalid.append((lineno, errors[0].message))
            continue
        records.append(rec)
    seqs = [r["seq"] for r in records if r["seq"] is not None]
    missing, dups = sequence_problems(seqs)
    return EventLogReport(
        records=records,
        invalid=invalid,
        missing_seq=missing,
        duplicate_seq=dups,
        error_records=sum(1 for r in records if r["decision"] == "error"),
    )
