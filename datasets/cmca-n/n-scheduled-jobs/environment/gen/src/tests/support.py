import copy
from datetime import datetime

BASE = {
    "docks": {
        "D01": {"bikes": 10, "capacity": 20},
        "D02": {"bikes": 3, "capacity": 12},
        "D03": {"bikes": 12, "capacity": 12},
    },
    "members": {
        "M1": {"balance_cents": 0, "plan": "monthly", "trips": 4},
        "M2": {"balance_cents": -250, "plan": "payg", "trips": 0},
    },
    "holds": {},
    "applied": {},
    "meta": {"rev": 7, "job": "holds", "at": "2027-01-04T08:50:03Z", "version": "4.2.0"},
}


def state(**changes) -> dict:
    out = copy.deepcopy(BASE)
    for key, value in changes.items():
        out[key] = value
    return out


def when(text: str) -> datetime:
    return datetime.fromisoformat(text)


def batch(kind: str, batch_id: str, records: list[dict]) -> dict:
    return {"batch": batch_id, "kind": kind, "records": records}
