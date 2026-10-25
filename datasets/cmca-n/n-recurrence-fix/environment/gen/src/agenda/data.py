"""The data directory (overview.md section 2)."""

import json
from functools import cached_property
from pathlib import Path

from .errors import EventError
from .events import model, window
from .zones import Zone, load as load_zones

def _read(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise EventError(f"no such file: {path.name}") from None
    except (ValueError, UnicodeDecodeError) as e:
        raise EventError(f"{path.name}: not UTF-8 JSON ({e})") from None

class DataSet:
    def __init__(self, root):
        self.root = Path(root)

    @cached_property
    def zones(self) -> dict[str, Zone]:
        return load_zones(_read(self.root / "zones.json"))

    @cached_property
    def window(self) -> window.Window:
        return window.load(_read(self.root / "agenda.json"))

    def uids(self) -> list[str]:
        return sorted(p.stem for p in (self.root / "events").glob("*.json"))

    def event(self, uid: str) -> model.Event:
        raw = _read(self.root / "events" / f"{uid}.json")
        event = model.load(raw, self.zones)
        if event.uid != uid:
            raise EventError(f"file {uid}.json holds {event.uid}")
        return event
