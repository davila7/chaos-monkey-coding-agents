"""[tenants.NAME]: API keys per tenant (docs/config.md, section 4)."""

from frontdoor.config import values
from frontdoor.errors import ConfigError


def parse(value) -> dict:
    t = values.table(value, "tenants")
    out = {}
    for name, entry in t.items():
        e = values.table(entry, f"tenants.{name}")
        values.only_keys(e, ["keys"], f"tenants.{name}")
        out[name] = tuple(values.string_list(e, "keys", f"tenants.{name}"))
    return out


def check_keys_unique(config) -> None:
    owner = {}
    for name, keys in config.tenants.items():
        for k in keys:
            if k in owner:
                raise ConfigError(f"API key {k!r} belongs to {owner[k]} and {name}")
            owner[k] = name
