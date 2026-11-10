"""Resolved text to typed values (types.md sections 3 to 8)."""

import re
from fractions import Fraction

from .errors import ConversionError

BOOLS = {"true": True, "yes": True, "on": True, "1": True, "false": False, "no": False, "off": False, "0": False}
DECIMAL = re.compile(r"[+-]?(?:0|[1-9](?:_?[0-9])*)")
HEX = re.compile(r"[+-]?0x[0-9A-Fa-f](?:_?[0-9A-Fa-f])*")

DURATION_PART = re.compile(r"([0-9]+)(ms|d|h|m|s)")
DURATION_UNITS = ["d", "h", "m", "s", "ms"]
DURATION_MS = {"d": 86_400_000, "h": 3_600_000, "m": 60_000, "s": 1000, "ms": 1}

SIZE = re.compile(r"([0-9]+)(?:\.([0-9]+))?(?: ?([KMGT]i?B|B))?")
SIZE_UNITS = {"B": 1, "KB": 1000, "MB": 1000 ** 2, "GB": 1000 ** 3, "TB": 1000 ** 4,
              "KiB": 1024, "MiB": 1024 ** 2, "GiB": 1024 ** 3, "TiB": 1024 ** 4}


def to_bool(text: str) -> bool:
    try:
        return BOOLS[text.lower()]
    except KeyError:
        raise ConversionError(f"not a bool: {text!r}") from None


def to_int(text: str) -> int:
    if DECIMAL.fullmatch(text):
        return int(text.replace("_", ""))
    if HEX.fullmatch(text):
        sign = -1 if text.startswith("-") else 1
        return sign * int(text.lstrip("+-")[2:].replace("_", ""), 16)
    raise ConversionError(f"not an int: {text!r}")


def to_duration(text: str) -> int:
    """Milliseconds."""
    total, pos, last = 0, 0, -1
    while pos < len(text):
        m = DURATION_PART.match(text, pos)
        if not m:
            raise ConversionError(f"not a duration: {text!r}")
        rank = DURATION_UNITS.index(m.group(2))
        if rank <= last:
            raise ConversionError(f"duration units out of order: {text!r}")
        last = rank
        total += int(m.group(1)) * DURATION_MS[m.group(2)]
        pos = m.end()
    if pos == 0:
        raise ConversionError("empty duration")
    return total


def to_size(text: str) -> int:
    """Bytes."""
    m = SIZE.fullmatch(text)
    if not m:
        raise ConversionError(f"not a size: {text!r}")
    amount = Fraction(int(m.group(1)))
    if m.group(2):
        amount += Fraction(int(m.group(2)), 10 ** len(m.group(2)))
    value = amount * SIZE_UNITS[m.group(3) or "B"]
    if value.denominator != 1:
        raise ConversionError(f"not a whole number of bytes: {text!r}")
    return int(value)


def to_list(text: str) -> list[str]:
    items = [item.strip() for item in text.split(",")]
    return [item for item in items if item]


CONVERTERS = {"string": str, "bool": to_bool, "int": to_int, "duration": to_duration, "size": to_size, "list": to_list}


def convert(type_name: str, text: str, where: str):
    if type_name == "string":
        return text
    try:
        return CONVERTERS[type_name](text.strip())
    except ConversionError as e:
        raise ConversionError(f"{where}: {e}") from None
