"""Item records (docs/catalog.md)."""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .errors import CatalogError

SKU = re.compile(r"^[A-Z]{3}-\d{4}$")
TAG = re.compile(r"^[a-z][a-z0-9-]{0,23}$")


@dataclass(frozen=True)
class Item:
    sku: str
    name: str
    weight_g: int
    dims_mm: tuple[int, int, int]
    tags: frozenset = field(default_factory=frozenset)
    zone: str | None = None
    lead_days: int = 14
    case_qty: int = 1

    def tag_list(self) -> list[str]:
        return sorted(self.tags)


def _int(rec, key, low, default=None):
    value = rec.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool) or value < low:
        raise CatalogError(f"{rec.get('sku', '?')}: {key} must be a whole number of at least {low}")
    return value


def item_from_record(rec: dict) -> Item:
    if not isinstance(rec, dict):
        raise CatalogError("an item record is a JSON object")
    sku = rec.get("sku")
    if not isinstance(sku, str) or not SKU.match(sku):
        raise CatalogError(f"bad sku {sku!r}")
    name = rec.get("name")
    if not isinstance(name, str) or not name.strip():
        raise CatalogError(f"{sku}: name is required")
    dims = rec.get("dims_mm")
    if not isinstance(dims, list) or len(dims) != 3 or not all(isinstance(d, int) and d > 0 for d in dims):
        raise CatalogError(f"{sku}: dims_mm takes three whole numbers above 0")
    tags = rec.get("tags", [])
    if not isinstance(tags, list) or not all(isinstance(t, str) and TAG.match(t) for t in tags):
        raise CatalogError(f"{sku}: tags are lower-case words")
    zone = rec.get("zone")
    if zone is not None and (not isinstance(zone, str) or not zone):
        raise CatalogError(f"{sku}: zone must be a non-empty string")
    return Item(
        sku=sku,
        name=name.strip(),
        weight_g=_int(rec, "weight_g", 1),
        dims_mm=tuple(dims),
        tags=frozenset(tags),
        zone=zone,
        lead_days=_int(rec, "lead_days", 0, 14),
        case_qty=_int(rec, "case_qty", 1, 1),
    )


class Catalog:
    def __init__(self, items=()):
        self._items: dict[str, Item] = {}
        for item in items:
            self.add(item)

    def add(self, item: Item) -> None:
        if item.sku in self._items:
            raise CatalogError(f"duplicate sku {item.sku}")
        self._items[item.sku] = item

    def get(self, sku: str) -> Item:
        try:
            return self._items[sku]
        except KeyError:
            raise CatalogError(f"unknown sku {sku}") from None

    def __contains__(self, sku) -> bool:
        return sku in self._items

    def __iter__(self):
        return iter(self._items[s] for s in sorted(self._items))

    def __len__(self) -> int:
        return len(self._items)

    def tagged(self, tag: str) -> list[Item]:
        return [i for i in self if tag in i.tags]

    @classmethod
    def load(cls, path: Path) -> "Catalog":
        try:
            records = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise CatalogError(f"cannot read {path}: {e}") from None
        if not isinstance(records, dict) or not isinstance(records.get("items"), list):
            raise CatalogError(f"{path}: expected an object with an items list")
        return cls(item_from_record(r) for r in records["items"])
