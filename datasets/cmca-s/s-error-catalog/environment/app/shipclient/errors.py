"""Error codes returned by our services, as published in the error catalog."""

from typing import NamedTuple


class ErrorInfo(NamedTuple):
    status: int
    retryable: bool
    message: str


ERRORS: dict[str, ErrorInfo] = {
    "AUTH-001": ErrorInfo(401, False, "Missing credentials"),
    "BIL-102": ErrorInfo(409, False, "Invoice already paid"),
    "PLT-901": ErrorInfo(500, False, "Internal error"),
}


def describe(code: str) -> ErrorInfo:
    """The catalog entry for `code`. Raises KeyError for a code the catalog does not define."""
    return ERRORS[code]
