"""Express: air network, next-day in Europe."""

from __future__ import annotations

from decimal import Decimal

from quoter.carriers.base import Carrier, Service


class Express(Carrier):
    name = "express"
    label = "Express"
    max_kg = Decimal(30)
    max_side_cm = Decimal(120)
    fuel_share = Decimal("1.2")
    services = (
        Service("next", "Next day", 1, Decimal("1.85")),
        Service("noon", "Next day by noon", 1, Decimal("2.40")),
        Service("2day", "Two day", 2, Decimal("1.45")),
    )

    def adjust(self, price: Decimal, zone: int, kg: Decimal) -> Decimal:
        # Light documents ship at a floor price.
        if kg <= Decimal("0.5"):
            return max(price * Decimal("0.75"), Decimal("9.90"))
        return price
