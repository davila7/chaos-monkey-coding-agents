"""Trial validation (SPEC 9.7): ATIF schema, manifest completeness, fault-log sequence."""

from __future__ import annotations

from pathlib import Path

from .events import read_event_log
from .ingest import Trial, events_path

MANIFEST = ("config.json", "result.json", "agent/trajectory.json")


def _atif_errors(path: Path) -> list[str] | None:
    """Harbor's ATIF validator errors, or None when Harbor is not installed."""
    try:
        from harbor.utils.trajectory_validator import TrajectoryValidator
    except ImportError:
        return None
    v = TrajectoryValidator()
    return [] if v.validate(path) else v.get_errors()


def validate(trial: Trial, trial_dir: Path) -> list[str]:
    problems = [f"missing {rel}" for rel in MANIFEST if not (trial_dir / rel).exists()]
    if trial.reward is not None and not events_path(trial_dir).exists():
        problems.append("missing fault log")
    traj = trial_dir / "agent/trajectory.json"
    if traj.exists():
        # Harbor is a workspace dependency (cmca-harbor), so CI always checks; a bare
        # install of cmca-analysis skips the check rather than failing every trial.
        errors = _atif_errors(traj)
        if errors:
            problems.append(f"atif: {errors[0]}")
    ev = events_path(trial_dir)
    if ev.exists():
        report = read_event_log(ev)
        if report.invalid:
            problems.append(f"fault log: {len(report.invalid)} invalid record(s)")
        if report.missing_seq:
            problems.append(f"fault log: missing seq {report.missing_seq[:5]}")
        if report.duplicate_seq:
            problems.append(f"fault log: duplicate seq {report.duplicate_seq[:5]}")
        if report.error_records:
            problems.append(f"fault log: {report.error_records} error record(s)")
    unjoined = sum(1 for f in trial.faults if f.call is None)
    if unjoined:
        problems.append(f"{unjoined} applied fault(s) without a matching call")
    return problems
