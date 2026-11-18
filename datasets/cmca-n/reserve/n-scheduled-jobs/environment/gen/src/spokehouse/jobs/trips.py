import copy
from datetime import datetime

from .. import fares
from ..errors import FeedError
from ..timeutil import fmt_ts, parse_ts

FEED = "trips"
FIELDS = ("trip", "member", "from", "to", "start", "end")


def duration(record: dict) -> int:
    seconds = (parse_ts(record["end"]) - parse_ts(record["start"])).total_seconds()
    return int(seconds)


def run(state: dict, batch: dict, now: datetime) -> dict:
    """Applies a batch of finished trips once (docs/jobs.md 2)."""
    out = copy.deepcopy(state)
    if batch["batch"] in out["applied"]:
        return out
    for record in batch["records"]:
        missing = [f for f in FIELDS if f not in record]
        if missing:
            raise FeedError(f"trip {record.get('trip')}: no {', '.join(missing)}")
        if record["member"] not in out["members"] or record["from"] not in out["docks"] or record["to"] not in out["docks"]:
            raise FeedError(f"trip {record['trip']}: unknown member or dock")
        seconds = duration(record)
        member = out["members"][record["member"]]
        out["docks"][record["from"]]["bikes"] -= 1
        out["docks"][record["to"]]["bikes"] += 1
        member["trips"] += 1
        member["balance_cents"] -= fares.fare(member["plan"], seconds)
    out["applied"][batch["batch"]] = fmt_ts(now)
    return out
