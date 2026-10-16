"""Countries quoter ships to: ISO code, name, region, EU membership, VAT."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Country:
    code: str
    name: str
    region: str
    eu: bool
    vat: bool = True


COUNTRIES = {
    c.code: c
    for c in (
        Country("AT", "Austria", "central", True),
        Country("BE", "Belgium", "west", True),
        Country("BG", "Bulgaria", "southeast", True),
        Country("CH", "Switzerland", "central", False),
        Country("CY", "Cyprus", "southeast", True),
        Country("CZ", "Czechia", "central", True),
        Country("DE", "Germany", "central", True),
        Country("DK", "Denmark", "north", True),
        Country("EE", "Estonia", "north", True),
        Country("ES", "Spain", "southwest", True),
        Country("FI", "Finland", "north", True),
        Country("FR", "France", "west", True),
        Country("GB", "United Kingdom", "west", False),
        Country("GR", "Greece", "southeast", True),
        Country("HR", "Croatia", "southeast", True),
        Country("HU", "Hungary", "central", True),
        Country("IE", "Ireland", "west", True),
        Country("IS", "Iceland", "north", False),
        Country("IT", "Italy", "south", True),
        Country("LI", "Liechtenstein", "central", False),
        Country("LT", "Lithuania", "north", True),
        Country("LU", "Luxembourg", "west", True),
        Country("LV", "Latvia", "north", True),
        Country("MT", "Malta", "south", True),
        Country("NL", "Netherlands", "west", True),
        Country("NO", "Norway", "north", False),
        Country("PL", "Poland", "central", True),
        Country("PT", "Portugal", "southwest", True),
        Country("RO", "Romania", "southeast", True),
        Country("RS", "Serbia", "southeast", False),
        Country("SE", "Sweden", "north", True),
        Country("SI", "Slovenia", "central", True),
        Country("SK", "Slovakia", "central", True),
        Country("TR", "Turkey", "southeast", False),
        Country("UA", "Ukraine", "east", False),
        Country("US", "United States", "overseas", False, vat=False),
        Country("CA", "Canada", "overseas", False, vat=False),
        Country("JP", "Japan", "overseas", False, vat=False),
        Country("AU", "Australia", "overseas", False, vat=False),
        Country("GI", "Gibraltar", "southwest", False, vat=False),
    )
}


def get(code: str) -> Country:
    try:
        return COUNTRIES[code.upper()]
    except KeyError:
        raise KeyError(f"unknown country {code!r}") from None
