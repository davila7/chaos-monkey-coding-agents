"""Field values: dotted paths into records and typed Python values (docs/store.md, section 3).

typed() turns the JSON value of a field into:

    string   -> str
    int      -> int
    decimal  -> decimal.Decimal with exactly `scale` fraction digits
    bool     -> bool
    date     -> datetime.date
    datetime -> datetime.datetime (naive, UTC)

A missing value and JSON null are both None.
"""

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from tally.errors import StoreError

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_DECIMAL = re.compile(r"^-?\d+\.\d+$")


def raw_value(record: dict, name: str):
    """The JSON value at a dotted path, or None when any step is missing."""
    node = record
    for part in name.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def parse_date(text: str) -> date:
    if not isinstance(text, str) or not _DATE.match(text):
        raise ValueError(f"not a date: {text!r}")
    return date.fromisoformat(text)


def parse_datetime(text: str) -> datetime:
    if not isinstance(text, str) or not _DATETIME.match(text):
        raise ValueError(f"not a datetime: {text!r}")
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")


def parse_decimal(text: str, scale: int) -> Decimal:
    if not isinstance(text, str) or not _DECIMAL.match(text):
        raise ValueError(f"not a decimal string: {text!r}")
    if len(text.split(".")[1]) != scale:
        raise ValueError(f"{text!r} does not have {scale} fraction digits")
    try:
        return Decimal(text)
    except InvalidOperation:
        raise ValueError(f"not a decimal: {text!r}") from None


def convert(field, raw):
    """JSON value -> typed value for one field; raises ValueError on a mismatch."""
    if raw is None:
        return None
    t = field.type
    if t == "string":
        if not isinstance(raw, str):
            raise ValueError(f"not a string: {raw!r}")
        return raw
    if t == "int":
        if isinstance(raw, bool) or not isinstance(raw, int):
            raise ValueError(f"not an integer: {raw!r}")
        return raw
    if t == "decimal":
        return parse_decimal(raw, field.scale)
    if t == "bool":
        if not isinstance(raw, bool):
            raise ValueError(f"not a boolean: {raw!r}")
        return raw
    if t == "date":
        return parse_date(raw)
    if t == "datetime":
        return parse_datetime(raw)
    raise ValueError(f"unknown type {t}")


def typed(record: dict, field):
    """Typed value of a field in a record; StoreError when the store is inconsistent."""
    try:
        value = convert(field, raw_value(record, field.name))
    except ValueError as e:
        raise StoreError(f"field {field.name}: {e}") from None
    if value is None and not field.nullable:
        raise StoreError(f"field {field.name} is null in a record but not nullable")
    return value
