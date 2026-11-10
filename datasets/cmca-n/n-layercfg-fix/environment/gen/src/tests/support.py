import shutil
import tempfile
from pathlib import Path

from layercfg.data import DataSet
from layercfg.report import resolve

APP = Path(__file__).resolve().parents[1]
DATA = APP / "data"
MINI = APP / "tests" / "fixtures" / "mini"


def dataset_with(configs: dict[str, str], shared: dict[str, str] | None = None, base: Path = MINI) -> tuple[DataSet, tempfile.TemporaryDirectory]:
    """A data directory with the schema and shared files of base, plus the given configs and shared files."""
    tmp = tempfile.TemporaryDirectory()
    root = Path(tmp.name)
    shutil.copyfile(base / "schema.json", root / "schema.json")
    shutil.copytree(base / "shared", root / "shared")
    for name, text in (shared or {}).items():
        (root / "shared" / name).write_text(text, encoding="utf-8")
    (root / "configs").mkdir()
    for cid, text in configs.items():
        (root / "configs" / f"{cid}.conf").write_text(text, encoding="utf-8")
    return DataSet(root), tmp


def resolved(text: str, shared: dict[str, str] | None = None) -> dict:
    """The resolved document of one config."""
    ds, tmp = dataset_with({"t-1": text}, shared)
    try:
        return resolve(ds, "t-1")
    finally:
        tmp.cleanup()


def settings(text: str, shared: dict[str, str] | None = None) -> dict:
    return resolved(text, shared)["settings"]
