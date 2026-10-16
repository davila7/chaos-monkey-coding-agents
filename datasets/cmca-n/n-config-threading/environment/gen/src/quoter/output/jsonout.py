"""JSON output. Every document echoes the settings that shaped the prices."""

from __future__ import annotations

import json

from quoter import settings
from quoter.core.money import format_plain

ECHO = ("currency", "rate_card", "fuel_pct", "tax_rate", "rounding", "round_step")


def _settings_echo() -> dict:
    values = vars(settings.SETTINGS)
    return {k: str(values[k]) for k in ECHO}


def _quote_dict(q) -> dict:
    return {
        "carrier": q.carrier,
        "service": q.service,
        "delivery": q.delivery.isoformat(),
        "zone": q.zone,
        "chargeable_kg": str(q.chargeable_kg),
        "box": q.box,
        "base": format_plain(q.base),
        "markup": format_plain(q.markup),
        "surcharges": list(q.surcharges),
        "fuel": format_plain(q.fuel),
        "insurance": format_plain(q.insurance),
        "net": format_plain(q.net),
        "tax": format_plain(q.tax),
        "gross": format_plain(q.gross),
        "currency": q.currency,
        "gross_local": format_plain(q.gross_local),
    }


def _dump(doc: dict) -> str:
    indent = settings.SETTINGS.json_indent or None
    return json.dumps(doc, indent=indent, ensure_ascii=False) + "\n"


def quotes_json(quotes: list, request) -> str:
    return _dump({"settings": _settings_echo(), "from": str(request.origin), "to": str(request.dest), "quotes": [_quote_dict(q) for q in quotes]})


def batch_json(result) -> str:
    lines = []
    for line in result.lines:
        entry = {"id": line.ident}
        if line.quote is None:
            entry["error"] = line.error
        else:
            entry["quote"] = _quote_dict(line.quote)
        lines.append(entry)
    return _dump(
        {
            "settings": _settings_echo(),
            "lines": lines,
            "net_total": format_plain(result.net_total),
            "discount_pct": str(result.discount_pct),
            "discount": format_plain(result.discount),
            "total": format_plain(result.total),
        }
    )
