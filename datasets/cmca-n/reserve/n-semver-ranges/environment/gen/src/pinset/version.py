"""Version numbers: parsing, precedence and text form (docs/versions.md)."""

import re
from functools import total_ordering

from pinset.errors import VersionError

NUMBER = r"0|[1-9][0-9]*"
PRE_ID = r"0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*"
BUILD_ID = r"[0-9A-Za-z-]+"
PRERELEASE = rf"(?:{PRE_ID})(?:\.(?:{PRE_ID}))*"
BUILD = rf"{BUILD_ID}(?:\.{BUILD_ID})*"
VERSION_RE = re.compile(rf"({NUMBER})\.({NUMBER})\.({NUMBER})(?:-({PRERELEASE}))?(?:\+({BUILD}))?")
PRERELEASE_RE = re.compile(PRERELEASE)
BUILD_RE = re.compile(BUILD)


@total_ordering
class Version:
    """A version. Build metadata is kept for the text form and ignored by every comparison."""

    __slots__ = ("major", "minor", "patch", "prerelease", "build", "_key")

    def __init__(self, major: int, minor: int, patch: int, prerelease=(), build=()):
        self.major, self.minor, self.patch = major, minor, patch
        self.prerelease = tuple(prerelease)
        self.build = tuple(build)
        self._key = (major, minor, patch, 0 if self.prerelease else 1, self.prerelease)

    @classmethod
    def parse(cls, text: str) -> "Version":
        if not isinstance(text, str):
            raise VersionError(f"not a version: {text!r}")
        m = VERSION_RE.fullmatch(text)
        if m is None:
            raise VersionError(f"not a version: {text!r}")
        pre = m.group(4).split(".") if m.group(4) else ()
        build = m.group(5).split(".") if m.group(5) else ()
        return cls(int(m.group(1)), int(m.group(2)), int(m.group(3)), pre, build)

    @property
    def release(self) -> tuple:
        """major, minor and patch."""
        return (self.major, self.minor, self.patch)

    def is_prerelease(self) -> bool:
        return bool(self.prerelease)

    def __eq__(self, other):
        if not isinstance(other, Version):
            return NotImplemented
        return self._key == other._key

    def __lt__(self, other):
        if not isinstance(other, Version):
            return NotImplemented
        return self._key < other._key

    def __hash__(self):
        return hash(self._key)

    def __str__(self):
        text = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            text += "-" + ".".join(self.prerelease)
        if self.build:
            text += "+" + ".".join(self.build)
        return text

    def __repr__(self):
        return f"Version({str(self)!r})"
