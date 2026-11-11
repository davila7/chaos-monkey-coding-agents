"""Numbers of members merged into another member, data/aliases.json (docs/data.md, section 4)."""

import json
from pathlib import Path

from clubroll import ids
from clubroll.errors import DataError


def load(path: Path) -> dict[int, int]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        raise DataError("aliases", f"cannot read {path}: {e}") from None
    if not isinstance(doc, dict):
        raise DataError("aliases", f"{path}: not an object")
    out = {}
    for k, v in doc.items():
        a, b = ids.number(k), ids.number(v) if isinstance(v, str) else None
        if a is None or b is None:
            raise DataError("aliases", f"{path}: bad entry {k!r}: {v!r}")
        out[a] = b
    return out


def resolve(aliases: dict[int, int], n: int) -> int:
    return aliases.get(n, n)


def save(path: Path, aliases: dict[int, int]) -> None:
    doc = {ids.fmt(k): ids.fmt(aliases[k]) for k in sorted(aliases)}
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
