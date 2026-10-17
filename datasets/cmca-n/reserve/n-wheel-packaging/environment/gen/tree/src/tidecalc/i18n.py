"""Translated labels, from locales/<lang>.properties."""

from __future__ import annotations

from functools import lru_cache
from importlib import resources

from tidecalc.errors import TideError


@lru_cache(maxsize=None)
def messages(lang: str) -> dict:
    path = resources.files("tidecalc").joinpath("locales", f"{lang}.properties")
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise TideError(f"no translations for {lang!r}") from None
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip()
    return out


def label(lang: str, key: str) -> str:
    return messages(lang).get(key, key)
