from pathlib import Path

import pytest

from cmca_harbor.conformance import task_chaos

ORIGINAL = "host = db-a\nport = 5432\nregion = west\n"


def task(tmp_path: Path, variant: str, source: str = "/app/conf/db.conf") -> Path:
    (tmp_path / "environment/conf").mkdir(parents=True)
    (tmp_path / "environment/conf/db.conf").write_text(ORIGINAL)
    (tmp_path / "variants").mkdir()
    (tmp_path / "variants/db.conf").write_text(variant)
    (tmp_path / "chaos.toml").write_text(
        'schema = "tt-task/1"\n\n[[poison]]\ntool = "shell"\n'
        f'source = "{source}"\nvariant = "variants/db.conf"\ntoken = "tok-123456"\n'
    )
    return tmp_path


def test_shell_source_is_bundled(tmp_path: Path) -> None:
    _, variants, sources = task_chaos(task(tmp_path, ORIGINAL.replace("5432", "6543 # tok-123456")))
    assert sources == {"variants/db.conf": ORIGINAL}
    assert "tok-123456" in variants["variants/db.conf"]


@pytest.mark.parametrize(
    ("variant", "message"),
    [
        (ORIGINAL + "extra\n", "line count"),
        (ORIGINAL, "changes 0 lines"),
        (ORIGINAL.replace("5432", "6543"), "carries the token"),
    ],
)
def test_shell_variant_rules(tmp_path: Path, variant: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        task_chaos(task(tmp_path, variant))


def test_shell_source_must_be_under_app(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="under /app"):
        task_chaos(task(tmp_path, ORIGINAL, source="/etc/db.conf"))
