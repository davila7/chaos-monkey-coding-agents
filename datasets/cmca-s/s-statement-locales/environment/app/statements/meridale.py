"""Monthly merchant statements from the Meridale settlements report."""

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, NamedTuple

BASE = "/v2"


@dataclass(frozen=True)
class Merchant:
    id: str
    tz: str  # as stored at sign-up: a zone name, or a fixed offset written UTC+HH:MM
    locale: str  # the account's POSIX locale, such as pt_BR.UTF-8
    currency: str  # settlement currency, ISO 4217


@dataclass(frozen=True)
class Line:
    day: date
    gross: Decimal
    fees: Decimal
    refunds: Decimal
    net: Decimal
    net_text: str  # the net as the Meridale dashboard writes it


@dataclass(frozen=True)
class Statement:
    merchant_id: str
    currency: str
    lines: tuple[Line, ...]
    total_net: Decimal
    total_text: str  # the total as the Meridale dashboard writes it


class Response(NamedTuple):
    status: int
    headers: dict[str, str]
    body: bytes


# Sends one request (method, path, query parameters, JSON body or None) and returns the response.
Transport = Callable[[str, str, dict[str, str], dict[str, Any] | None], Response]


class ApiError(Exception):
    """An error response: its HTTP status and the error code from its body."""

    def __init__(self, status: int, code: str):
        super().__init__(f"{status} {code}")
        self.status = status
        self.code = code


def _call(transport: Transport, method: str, path: str, params: dict[str, str] | None = None, body: dict[str, Any] | None = None) -> Any:
    r = transport(method, path, dict(params or {}), body)
    if r.status != 200:
        try:
            code = str(json.loads(r.body)["error"]["code"])
        except (ValueError, KeyError, TypeError):
            code = ""
        raise ApiError(r.status, code)
    return json.loads(r.body)


def _amount(value: str) -> Decimal:
    return Decimal(str(round(float(value), 2)))


def monthly_statement(transport: Transport, merchant: Merchant, year: int, month: int) -> Statement:
    """The statement of `merchant` for one calendar month, with its days in the merchant's time zone.

    One line per day that has settlements, in day order, with the figures and the text the
    Meridale dashboard shows. Raises ApiError when the API answers with an error.
    """
    first = date(year, month, 1)
    last = date(year + month // 12, month % 12 + 1, 1) - timedelta(days=1)
    params = {
        "merchant_id": merchant.id,
        "tz": merchant.tz,
        "from": first.isoformat(),
        "to": last.isoformat(),
        "lang": merchant.locale[:2],
        "format": "display",
    }
    report = _call(transport, "GET", f"{BASE}/settlements", params)
    lines = []
    for d in report["days"]:
        gross, fees, refunds = _amount(d["gross"]), _amount(d["fees"]), _amount(d["refunds"])
        lines.append(Line(date.fromisoformat(d["day"]), gross, fees, refunds, gross - fees - refunds, d["display_net"]))
    total = sum((line.net for line in lines), Decimal(0))
    return Statement(merchant.id, report["currency"], tuple(lines), total, f"{report['currency']} {total:,.2f}")
