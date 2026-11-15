import json
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from retain.data import DataSet
from retain.plan import plan
from retain.zones import load_zones

APP = Path(__file__).resolve().parents[1]
DATA = APP / "data"
MINI = APP / "tests" / "fixtures" / "mini"
UTC = timezone.utc


def zones() -> dict:
    return load_zones(json.loads((MINI / "zones.json").read_text(encoding="utf-8")))


def at(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def dataset_with(sets: dict[str, dict], zone_table: dict | None = None) -> tuple[DataSet, tempfile.TemporaryDirectory]:
    """A data directory with the zones of the mini fixture (or the given table) and the given sets."""
    tmp = tempfile.TemporaryDirectory()
    root = Path(tmp.name)
    if zone_table is None:
        shutil.copyfile(MINI / "zones.json", root / "zones.json")
    else:
        (root / "zones.json").write_text(json.dumps(zone_table), encoding="utf-8")
    (root / "sets").mkdir()
    for sid, doc in sets.items():
        (root / "sets" / f"{sid}.json").write_text(json.dumps(doc), encoding="utf-8")
    return DataSet(root), tmp


def plan_of(doc: dict, zone_table: dict | None = None) -> dict:
    """The plan of one set."""
    ds, tmp = dataset_with({"t-1": doc}, zone_table)
    try:
        return plan(ds, "t-1")
    finally:
        tmp.cleanup()


def kept(doc: dict) -> dict[str, list[str]]:
    return {k["name"]: k["reasons"] for k in plan_of(doc)["keep"]}


def series(prefix: str, first: str, step_hours: float, count: int, ext: str = ".tar") -> list[str]:
    """Names with Z stamps, every step_hours from first."""
    t = at(first)
    return [f"{prefix}-{(t + timedelta(hours=step_hours * i)).strftime('%Y%m%dT%H%M%S')}Z{ext}" for i in range(count)]
