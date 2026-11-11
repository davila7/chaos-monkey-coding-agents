"""Merging assignments and resolving references (interp.md)."""

import re

from .errors import InterpolationError
from .lexer import NAME
from .loader import Assignment

REF_NAME = re.compile(r"(?:(" + NAME + r")\.)?([A-Za-z0-9_-]+)")
FALLBACK = "defaults"

Store = dict[str, dict[str, Assignment]]


def merge(assignments: list[Assignment]) -> Store:
    """The last assignment of a key wins (syntax.md 4.4, include.md 2.3)."""
    store: Store = {}
    for a in assignments:
        store.setdefault(a.section, {})[a.key] = a
    return store


class Resolver:
    def __init__(self, store: Store):
        self.store = store
        self._done: dict[tuple[str, str], str] = {}

    def value(self, section: str, key: str, stack: tuple = ()) -> str:
        a = self.store.get(section, {}).get(key)
        if a is None:
            raise InterpolationError(f"no key {key!r} in section [{section}]")
        if not a.interp:
            return a.text
        if (section, key) in self._done:
            return self._done[(section, key)]
        if (section, key) in stack:
            chain = " -> ".join(f"{s}.{k}" for s, k in stack + ((section, key),))
            raise InterpolationError(f"{a.where}: reference cycle {chain}")
        text = self.expand(section, a.text, stack + ((section, key),), a.where)
        self._done[(section, key)] = text
        return text

    def lookup(self, section: str, name: str, stack: tuple, where: str) -> str:
        m = REF_NAME.fullmatch(name)
        if not m:
            raise InterpolationError(f"{where}: bad reference ${{{name}}}")
        if "." in name:
            target, key = name.rsplit(".", 1)
            target = target.lower()
        else:
            key = name
            target = section if key in self.store.get(section, {}) else FALLBACK
        if key not in self.store.get(target, {}):
            raise InterpolationError(f"{where}: ${{{name}}} names no key")
        return self.value(target, key, stack)

    def expand(self, section: str, text: str, stack: tuple, where: str) -> str:
        out, i = [], 0
        while i < len(text):
            if text.startswith("$$", i):
                out.append("$")
                i += 2
            elif text.startswith("${", i):
                end = text.find("}", i + 2)
                if end < 0:
                    raise InterpolationError(f"{where}: unclosed reference")
                out.append(self.lookup(section, text[i + 2:end], stack, where))
                i = end + 1
            else:
                out.append(text[i])
                i += 1
        return "".join(out)

