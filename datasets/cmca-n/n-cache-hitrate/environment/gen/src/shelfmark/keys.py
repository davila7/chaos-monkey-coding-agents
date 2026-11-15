"""Cache keys (docs/cache.md 2)."""

from urllib.parse import parse_qsl

from . import locale


def parse_query(query: str) -> list[tuple[str, str]]:
    return parse_qsl(query, keep_blank_values=True)


def normalize_q(value: str) -> str:
    return " ".join(value.lower().split())


def key_params(params, cfg) -> str:
    kept = []
    for name, value in params:
        if name in cfg.ignore_params or name.startswith("utm_"):
            continue
        if name == "q":
            value = normalize_q(value)
        kept.append((name, value))
    return "&".join(f"{name}={value}" for name, value in sorted(kept))


def build(route: str, ident: str, params, accept_language: str | None, cfg) -> str:
    lang = ""
    if "Accept-Language" in cfg.routes[route].vary:
        lang = locale.negotiate(accept_language, cfg.locales, cfg.default_locale)
    return f"{route}|{ident}|{key_params(params, cfg)}|{lang}"
