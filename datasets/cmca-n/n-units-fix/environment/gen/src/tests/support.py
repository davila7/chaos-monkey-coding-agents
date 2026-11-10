import json
import tempfile
from pathlib import Path

from measure.data import DataSet
from measure.expr import parse_unit
from measure.quantity import parse_quantity
from measure.table import Table

APP = Path(__file__).resolve().parents[1]
DATA = APP / "data"
MINI = APP / "tests" / "fixtures" / "mini"


def mini() -> Table:
    return Table(json.loads((MINI / "units.json").read_text(encoding="utf-8")))


def unit(text: str):
    return parse_unit(text, mini())


def quantity(text: str):
    return parse_quantity(text, mini())


def dataset_with(records=(), base: Path = MINI) -> tuple[DataSet, tempfile.TemporaryDirectory]:
    """A data directory with the units table of base and the given records."""
    tmp = tempfile.TemporaryDirectory()
    root = Path(tmp.name)
    (root / "units.json").write_text((base / "units.json").read_text(encoding="utf-8"), encoding="utf-8")
    (root / "records").mkdir()
    for rec in records:
        (root / "records" / f"{rec['id']}.json").write_text(json.dumps(rec), encoding="utf-8")
    return DataSet(root), tmp
