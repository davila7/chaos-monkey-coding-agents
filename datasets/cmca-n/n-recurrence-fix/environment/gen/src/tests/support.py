import json
import tempfile
from pathlib import Path

from agenda.data import DataSet

APP = Path(__file__).resolve().parents[1]
DATA = APP / "data"
MINI = APP / "tests" / "fixtures" / "mini"


def mini() -> DataSet:
    return DataSet(MINI)


def dataset_with(events=(), window=None, base: Path = MINI) -> tuple[DataSet, tempfile.TemporaryDirectory]:
    """A copy of a data directory's tables with the given events."""
    tmp = tempfile.TemporaryDirectory()
    root = Path(tmp.name)
    (root / "zones.json").write_text((base / "zones.json").read_text(encoding="utf-8"), encoding="utf-8")
    agenda = (base / "agenda.json").read_text(encoding="utf-8") if window is None else json.dumps({"from": window[0], "to": window[1]})
    (root / "agenda.json").write_text(agenda, encoding="utf-8")
    (root / "events").mkdir()
    for e in events:
        (root / "events" / f"{e['uid']}.json").write_text(json.dumps(e), encoding="utf-8")
    return DataSet(root), tmp
