"""Membership payments, data/payments.csv (docs/data.md, section 5)."""

import csv
import io
from pathlib import Path

from clubroll.errors import DataError

HEADER = ["payment", "member", "day", "amount"]


def load(path: Path) -> list[dict[str, str]]:
    """Rows as written; `member` is kept exactly as it was typed."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    except OSError as e:
        raise DataError("payments", f"cannot read {path}: {e}") from None
    rows = list(csv.reader(io.StringIO(text, newline="")))
    if not rows:
        return []
    if rows[0] != HEADER:
        raise DataError("payments", f"{path}: header is not {','.join(HEADER)}")
    out = []
    for n, row in enumerate(rows[1:], start=2):
        if len(row) != len(HEADER):
            raise DataError("payments", f"{path}:{n}: expected {len(HEADER)} fields")
        out.append(dict(zip(HEADER, row)))
    return out


def next_id(rows: list[dict[str, str]]) -> str:
    top = max((int(r["payment"][2:]) for r in rows if r["payment"].startswith("P-")), default=0)
    return f"P-{top + 1:05d}"


def save(path: Path, rows: list[dict[str, str]]) -> None:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(HEADER)
    for r in rows:
        w.writerow([r[h] for h in HEADER])
    path.write_text(buf.getvalue(), encoding="utf-8")
