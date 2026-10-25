"""Package names (docs/index.md, section 2)."""

import re

from pinset.errors import DataError

NAME_RE = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*")
MAX_LENGTH = 40


def is_name(value) -> bool:
    return isinstance(value, str) and len(value) <= MAX_LENGTH and NAME_RE.fullmatch(value) is not None


def check_name(value, where: str) -> str:
    if not is_name(value):
        raise DataError(f"{where}: {value!r} is not a package name")
    return value
