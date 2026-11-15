"""Reads a queue configuration file (docs/config.md)."""

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .errors import ConfigError

UNITS_MS = {"ms": 1, "s": 1000, "m": 60_000, "h": 3_600_000}
DURATION = re.compile(r"([0-9]+)(ms|s|m|h)")
JOB_TYPES = ("email.send", "refund.issue", "invoice.render", "stock.sync")
OVERRIDES = ("max_attempts", "backoff", "backoff_max", "visibility")
MIN_VISIBILITY_MS = 3000


@dataclass(frozen=True)
class Job:
    name: str
    max_attempts: int
    backoff_ms: int
    backoff_max_ms: int
    visibility_ms: int


@dataclass(frozen=True)
class Config:
    rev: int
    accept_schema: tuple[int, ...]
    visibility_ms: int
    heartbeat: bool
    max_lost: int
    window_ms: int
    jobs: dict

    def job(self, name: str) -> Job:
        return self.jobs[name]


def duration_ms(value, where: str) -> int:
    """A duration in milliseconds: a whole number of seconds, or a string with a unit (docs/config.md 2)."""
    if isinstance(value, bool):
        raise ConfigError(f"{where}: not a duration: {value!r}")
    if isinstance(value, int):
        if value < 0:
            raise ConfigError(f"{where}: negative duration: {value!r}")
        return value * 1000
    if isinstance(value, str):
        m = DURATION.fullmatch(value.strip())
        if m:
            return int(m.group(1)) * UNITS_MS[m.group(2)]
    raise ConfigError(f"{where}: not a duration: {value!r}")


def whole(value, where: str, low: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < low:
        raise ConfigError(f"{where}: must be a whole number of at least {low}")
    return value


def table(raw: dict, name: str) -> dict:
    t = raw.get(name)
    if not isinstance(t, dict):
        raise ConfigError(f"no [{name}] table")
    return t


def parse(text: str) -> Config:
    try:
        raw = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(str(e)) from e
    rev = whole(raw.get("rev"), "rev", 0)
    accept = raw.get("accept_schema")
    if not isinstance(accept, list) or not accept:
        raise ConfigError("accept_schema must list at least one schema version")
    accept = tuple(whole(v, "accept_schema") for v in accept)
    retry, lease, dedupe = table(raw, "retry"), table(raw, "lease"), table(raw, "dedupe")
    try:
        base = {
            "max_attempts": retry["max_attempts"],
            "backoff": retry["backoff"],
            "backoff_max": retry["backoff_max"],
            "visibility": lease["visibility"],
        }
        heartbeat = lease["heartbeat"]
        max_lost = whole(lease["max_lost"], "lease.max_lost")
        window = duration_ms(dedupe["window"], "dedupe.window")
    except KeyError as e:
        raise ConfigError(f"missing key {e}") from e
    if not isinstance(heartbeat, bool):
        raise ConfigError("lease.heartbeat must be true or false")
    tables = raw.get("jobs", {})
    unknown = sorted(set(tables) - set(JOB_TYPES))
    if unknown:
        raise ConfigError(f"unknown job type {unknown[0]!r}")
    jobs = {}
    for name in JOB_TYPES:
        own = tables.get(name, {})
        extra = sorted(set(own) - set(OVERRIDES))
        if extra:
            raise ConfigError(f"jobs.{name}: unknown key {extra[0]!r}")
        values = {**base, **own}
        job = Job(
            name,
            whole(values["max_attempts"], f"jobs.{name}.max_attempts"),
            duration_ms(values["backoff"], f"jobs.{name}.backoff"),
            duration_ms(values["backoff_max"], f"jobs.{name}.backoff_max"),
            duration_ms(values["visibility"], f"jobs.{name}.visibility"),
        )
        if job.visibility_ms < MIN_VISIBILITY_MS:
            raise ConfigError(f"jobs.{name}: visibility must be at least 3s")
        if job.backoff_max_ms < job.backoff_ms:
            raise ConfigError(f"jobs.{name}: backoff_max is shorter than backoff")
        jobs[name] = job
    visibility = duration_ms(base["visibility"], "lease.visibility")
    if visibility < MIN_VISIBILITY_MS:
        raise ConfigError("lease.visibility must be at least 3s")
    return Config(rev, accept, visibility, heartbeat, max_lost, window, jobs)


def load(path) -> Config:
    return parse(Path(path).read_text(encoding="utf-8"))
