"""The data directory (overview.md section 2)."""

import json
from functools import cached_property
from pathlib import Path

from .errors import RecordError, UnitError
from .records import Record, load
from .table import Table


def _read(path: Path, error):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise error(f"no such file: {path.name}") from None
    except (ValueError, UnicodeDecodeError) as e:
        raise error(f"{path.name}: not UTF-8 JSON ({e})") from None


class DataSet:
    def __init__(self, root):
        self.root = Path(root)

    @cached_property
    def table(self) -> Table:
        return Table(_read(self.root / "units.json", UnitError))

    def ids(self) -> list[str]:
        return sorted(p.stem for p in (self.root / "records").glob("*.json"))

    def record(self, rid: str) -> Record:
        rec = load(_read(self.root / "records" / f"{rid}.json", RecordError))
        if rec.id != rid:
            raise RecordError(f"file {rid}.json holds {rec.id}")
        return rec
