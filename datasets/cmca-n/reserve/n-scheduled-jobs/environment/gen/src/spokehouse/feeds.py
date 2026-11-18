import json
from pathlib import Path

from .errors import FeedError

KINDS = ("trips", "holds", "rebalance")


def read_batch(path) -> dict:
    """A feed file: a header line, then one record per line (docs/feeds.md)."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    if not lines:
        raise FeedError(f"{path}: empty feed")
    try:
        header = json.loads(lines[0])
    except json.JSONDecodeError as e:
        raise FeedError(f"{path}: line 1: {e.msg}") from None
    if not isinstance(header, dict) or header.get("kind") not in KINDS or not isinstance(header.get("batch"), str):
        raise FeedError(f"{path}: line 1: not a batch header")
    records = []
    for number, line in enumerate(lines[1:], start=2):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as e:
            raise FeedError(f"{path}: line {number}: {e.msg}") from None
        if not isinstance(record, dict):
            raise FeedError(f"{path}: line {number}: not an object")
        records.append(record)
    if header.get("count") != len(records):
        raise FeedError(f"{path}: header says {header.get('count')} records, found {len(records)}")
    return {"batch": header["batch"], "kind": header["kind"], "records": records}
