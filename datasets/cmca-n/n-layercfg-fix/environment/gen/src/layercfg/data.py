"""The data directory (overview.md section 2)."""

import json
from functools import cached_property
from pathlib import Path

from .errors import IncludeError, ParseError, SchemaError
from .schema import Schema


def _read(path: Path, error) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise error(f"no such file: {path.parent.name}/{path.name}") from None
    except UnicodeDecodeError:
        raise error(f"{path.parent.name}/{path.name}: not UTF-8") from None


class DataSet:
    def __init__(self, root):
        self.root = Path(root)

    @cached_property
    def schema(self) -> Schema:
        try:
            raw = json.loads((self.root / "schema.json").read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise SchemaError("no such file: schema.json") from None
        except (ValueError, UnicodeDecodeError) as e:
            raise SchemaError(f"schema.json: not UTF-8 JSON ({e})") from None
        return Schema(raw)

    def ids(self) -> list[str]:
        return sorted(p.stem for p in (self.root / "configs").glob("*.conf"))

    def config_text(self, cid: str) -> str:
        return _read(self.root / "configs" / f"{cid}.conf", ParseError)

    def shared_text(self, name: str) -> str:
        return _read(self.root / "shared" / name, IncludeError)
