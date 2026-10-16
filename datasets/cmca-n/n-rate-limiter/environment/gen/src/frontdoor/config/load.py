"""Loading a configuration file (docs/config.md).

The file is TOML. Each top-level table or array of tables is a section; the
parser of a section is looked up in frontdoor.config.sections.SECTIONS, and a
section that is not listed there is an error. After every section is parsed,
the checks in sections.CHECKS run on the whole configuration (for rules that
relate two sections).
"""

import tomllib
from pathlib import Path

from frontdoor.config import sections
from frontdoor.errors import ConfigError


class Config:
    def __init__(self, path: Path, data: dict):
        self.path = path
        self.data = data

    def section(self, name: str, missing=None):
        """The parsed value of a section, or `missing` when the file has no such section."""
        return self.data.get(name, missing)

    @property
    def routes(self):
        return self.data["route"]

    @property
    def tenants(self):
        return self.data.get("tenants", {})

    @property
    def server(self):
        return self.data.get("server") or sections.server.Server("edge")

    @property
    def upstream(self):
        return self.data.get("upstream") or sections.upstream.Upstream(2000)


def load_config(path) -> Config:
    path = Path(path)
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError(f"{path}: no such file") from None
    except (OSError, UnicodeDecodeError) as e:
        raise ConfigError(f"{path}: cannot read: {e}") from None
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path}: not valid TOML: {e}") from None
    data = {}
    for name, value in raw.items():
        parser = sections.SECTIONS.get(name)
        if parser is None:
            raise ConfigError(f"{path}: unknown section [{name}]")
        try:
            data[name] = parser(value)
        except ConfigError as e:
            raise ConfigError(f"{path}: [{name}] {e}") from None
    for name in sections.REQUIRED:
        if name not in data:
            raise ConfigError(f"{path}: no [{name}] section")
    config = Config(path, data)
    for check in sections.CHECKS:
        try:
            check(config)
        except ConfigError as e:
            raise ConfigError(f"{path}: {e}") from None
    return config
