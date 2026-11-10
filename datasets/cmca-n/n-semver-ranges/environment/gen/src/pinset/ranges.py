"""Version ranges, as written in manifests and in index dependencies.

Release 1.x: a range is one version (`1.4.2`, `=1.4.2`) or a lower bound
(`>=1.4.2`).
"""

from pinset.errors import RangeError, VersionError
from pinset.version import Version


class Range:
    def __init__(self, text: str, op: str, version: Version):
        self.text = text
        self.op = op
        self.version = version

    def test(self, version: Version) -> bool:
        """True when `version` satisfies the range."""
        if self.op == "=":
            return version == self.version
        if version.is_prerelease():
            return False
        return version >= self.version

    def is_exact(self) -> bool:
        """True for a range that names one version (docs/resolve.md, section 4)."""
        return self.op == "="

    def __str__(self):
        return f"{self.op}{self.version}"


def parse_range(text: str) -> Range:
    if not isinstance(text, str):
        raise RangeError("bad-range", f"a range is a string, not {type(text).__name__}")
    body = text.strip()
    if not body:
        raise RangeError("bad-range", "empty range")
    if body.startswith(">="):
        op, body = ">=", body[2:]
    elif body.startswith("="):
        op, body = "=", body[1:]
    else:
        op = "="
    if not body or not body[0].isdigit():
        raise RangeError("bad-range", f"unsupported range {text!r}")
    try:
        version = Version.parse(body)
    except VersionError as e:
        raise RangeError("bad-version", str(e)) from None
    return Range(text, op, version)
