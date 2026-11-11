"""Reads a cache configuration file (docs/config.md)."""

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .errors import ConfigError
from .routes import ROUTES

UNITS_MS = {"ms": 1, "s": 1000, "m": 60_000, "h": 3_600_000}
DURATION = re.compile(r"([0-9]+)(ms|s|m|h)")
VARY = ("Accept-Language",)


@dataclass(frozen=True)
class Route:
    name: str
    ttl_ms: int
    vary: tuple[str, ...]


@dataclass(frozen=True)
class Config:
    rev: int
    locales: tuple[str, ...]
    default_locale: str
    ignore_params: frozenset[str]
    routes: dict[str, Route]


def parse_duration_ms(value) -> int:
    """The ttl of a route in milliseconds (docs/config.md 3)."""
    if isinstance(value, bool):
        raise ConfigError(f"not a duration: {value!r}")
    if isinstance(value, int):
        if value < 0:
            raise ConfigError(f"negative duration: {value!r}")
        return value * 1000
    if isinstance(value, str):
        m = DURATION.fullmatch(value.strip())
        if m:
            return int(m.group(1)) * UNITS_MS[m.group(2)]
    raise ConfigError(f"not a duration: {value!r}")


def parse(text: str) -> Config:
    try:
        raw = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(str(e)) from e
    try:
        rev = raw["rev"]
        locales = tuple(raw["locales"])
        default = raw["default_locale"]
        ignore = frozenset(raw.get("ignore_params", []))
        tables = raw["routes"]
    except KeyError as e:
        raise ConfigError(f"missing key {e}") from e
    if not isinstance(rev, int) or isinstance(rev, bool):
        raise ConfigError("rev must be a whole number")
    if not locales or default not in locales:
        raise ConfigError("default_locale must be one of locales")
    routes = {}
    for name in ROUTES:
        table = tables.get(name)
        if table is None:
            raise ConfigError(f"no [routes.{name}] table")
        vary = tuple(table.get("vary", []))
        for header in vary:
            if header not in VARY:
                raise ConfigError(f"routes.{name}: cannot vary on {header!r}")
        if "ttl" not in table:
            raise ConfigError(f"routes.{name}: no ttl")
        routes[name] = Route(name, parse_duration_ms(table["ttl"]), vary)
    return Config(rev, locales, default, ignore, routes)


def load(path) -> Config:
    return parse(Path(path).read_text(encoding="utf-8"))
