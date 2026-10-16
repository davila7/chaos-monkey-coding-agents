"""The locale table shipped in locales/ (docs/locales.md)."""

import json
from dataclasses import dataclass
from pathlib import Path

from tally.errors import UsageError

LOCALE_DIR = Path(__file__).resolve().parents[2] / "locales"
KEYS = ("name", "decimal", "group", "group_sizes", "min_grouping", "minus", "date", "datetime", "true", "false")


@dataclass(frozen=True)
class Locale:
    name: str
    decimal: str
    group: str
    group_sizes: tuple[int, ...]
    min_grouping: int
    minus: str
    date: str
    datetime: str
    true: str
    false: str


def available() -> list[str]:
    return sorted(p.stem for p in LOCALE_DIR.glob("*.json"))


def load_locale(name: str) -> Locale:
    path = LOCALE_DIR / f"{name}.json"
    if "/" in name or not path.is_file():
        raise UsageError(f"unknown locale {name!r} (known: {', '.join(available())})")
    raw = json.loads(path.read_text(encoding="utf-8"))
    missing = [k for k in KEYS if k not in raw]
    if missing:
        raise UsageError(f"locale {name} lacks {', '.join(missing)}")
    sizes = tuple(int(s) for s in raw["group_sizes"])
    if not sizes or any(s < 1 for s in sizes):
        raise UsageError(f"locale {name}: bad group_sizes")
    return Locale(raw["name"], raw["decimal"], raw["group"], sizes, int(raw["min_grouping"]), raw["minus"],
                  raw["date"], raw["datetime"], raw["true"], raw["false"])
