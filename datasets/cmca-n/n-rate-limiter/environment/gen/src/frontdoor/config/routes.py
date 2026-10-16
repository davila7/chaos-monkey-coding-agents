"""[[route]]: the route table (docs/config.md, section 3)."""

from dataclasses import dataclass

from frontdoor.config import values
from frontdoor.errors import ConfigError
from frontdoor.http.paths import split_segments

KEYS = ["name", "prefix", "methods", "public", "status"]


@dataclass(frozen=True)
class Route:
    name: str
    prefix: str
    segments: tuple
    methods: tuple
    public: bool
    status: int


def parse(value) -> list:
    out = []
    for i, t in enumerate(values.tables(value, "route"), 1):
        what = f"route {i}"
        values.only_keys(t, KEYS, what)
        name = values.string(t, "name", what)
        prefix = values.string(t, "prefix", what)
        if not prefix.startswith("/"):
            raise ConfigError(f"route {name}: prefix must start with /")
        methods = values.string_list(t, "methods", f"route {name}", required=False, missing=["GET"])
        status = t.get("status", 200)
        if not isinstance(status, int) or isinstance(status, bool) or not 200 <= status <= 299:
            raise ConfigError(f"route {name}: status must be a 2xx integer")
        out.append(Route(name, prefix, split_segments(prefix), tuple(m.upper() for m in methods),
                         values.boolean(t, "public", f"route {name}"), status))
    return out


def check_unique(config) -> None:
    seen = set()
    for r in config.routes:
        if r.name in seen:
            raise ConfigError(f"route name {r.name!r} is used twice")
        seen.add(r.name)
