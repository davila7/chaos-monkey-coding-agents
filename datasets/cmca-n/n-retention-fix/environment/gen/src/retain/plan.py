"""Plans and the summary listing (output.md sections 2 and 3)."""

from .data import DataSet
from .names import iso, parse_name
from .rules import newest_first, select
from .sets import BackupSet


def make_plan(s: BackupSet) -> dict:
    backups, ignored = [], []
    for name in s.files:
        b = parse_name(name, s.prefix, s.zone)
        if b is None:
            ignored.append(name)
        else:
            backups.append(b)
    reasons = select(s.policy, backups, s.pins, s.now)
    order = newest_first(backups)
    keep = [{"name": b.name, "at": iso(b.at), "reasons": reasons[b.name]} for b in order if reasons[b.name]]
    prune = [b.name for b in order if not reasons[b.name]]
    names = {b.name for b in backups}
    missing = sorted({p for p in s.pins if p not in names})
    return {"set": s.sid, "zone": s.zone.zid, "now": iso(s.now), "keep": keep, "prune": prune, "ignored": sorted(ignored), "missing_pins": missing}


def plan(ds: DataSet, sid: str) -> dict:
    return make_plan(ds.load(sid))


def summary_rows(plans: list[dict]) -> list[dict]:
    rows = [{"set": p["set"], "kept": len(p["keep"]), "pruned": len(p["prune"]), "ignored": len(p["ignored"]), "missing_pins": len(p["missing_pins"])} for p in plans]
    rows.sort(key=lambda r: r["set"])
    return rows
