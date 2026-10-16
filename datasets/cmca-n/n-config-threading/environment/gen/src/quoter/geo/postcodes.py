"""Addresses as COUNTRY-POSTCODE, and remote-area postcodes."""

from __future__ import annotations

import re
from dataclasses import dataclass

from quoter.core.errors import QuoteError
from quoter.geo import countries

# Postcode prefixes of areas that carriers treat as remote.
REMOTE = {
    "GB": ("HS", "ZE", "KW15", "KW16", "KW17", "PA20", "PH4"),
    "FR": ("20",),
    "DE": ("18565", "25846", "25847", "25849", "26474", "26486"),
    "IT": ("07", "09", "98", "90", "91", "92"),
    "ES": ("35", "38", "07", "51", "52"),
    "NO": ("93", "94", "95", "96", "97", "98", "99"),
    "PT": ("90", "95", "97"),
    "DK": ("37", "39"),
    "GR": ("81", "82", "83", "84", "85"),
    "FI": ("22",),
}

_FORMS = {
    "GB": re.compile(r"^[A-Z]{1,2}[0-9][A-Z0-9]? ?[0-9][A-Z]{2}$"),
    "NL": re.compile(r"^[0-9]{4} ?[A-Z]{2}$"),
    "PT": re.compile(r"^[0-9]{4}-?[0-9]{3}$"),
    "PL": re.compile(r"^[0-9]{2}-?[0-9]{3}$"),
    "CA": re.compile(r"^[A-Z][0-9][A-Z] ?[0-9][A-Z][0-9]$"),
}


@dataclass(frozen=True)
class Address:
    country: str
    postcode: str

    def __str__(self) -> str:
        return f"{self.country}-{self.postcode}"


def parse_address(text: str) -> Address:
    """'de-10115' -> Address('DE', '10115'). The postcode is upper-cased and
    checked against the country's form where one is known."""
    raw = text.strip().upper()
    if "-" not in raw:
        raise QuoteError(f"address must be COUNTRY-POSTCODE: {text!r}")
    code, postcode = raw.split("-", 1)
    try:
        countries.get(code)
    except KeyError as exc:
        raise QuoteError(str(exc.args[0])) from None
    postcode = postcode.strip()
    form = _FORMS.get(code)
    if form is not None and not form.match(postcode):
        raise QuoteError(f"postcode {postcode!r} is not valid for {code}")
    if form is None and not re.match(r"^[A-Z0-9 -]{2,10}$", postcode):
        raise QuoteError(f"postcode {postcode!r} is not valid for {code}")
    return Address(code, postcode)


def is_remote(address: Address) -> bool:
    prefixes = REMOTE.get(address.country, ())
    compact = address.postcode.replace(" ", "")
    return any(compact.startswith(p) for p in prefixes)
