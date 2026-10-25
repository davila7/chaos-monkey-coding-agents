class StockroomError(Exception):
    """Base class for every error the package raises on purpose."""


class SettingsError(StockroomError):
    """An unknown setting or a value of the wrong kind."""


class CatalogError(StockroomError):
    """An item record that breaks catalog.md."""


class BinError(StockroomError):
    """A bin code or layout that breaks bins.md."""


class NoBinError(BinError):
    """No free bin can take the item."""


class LedgerError(StockroomError):
    """A movement that would break the ledger rules (stock.md)."""


class RateError(StockroomError):
    """A rate table or a quote request that breaks rates.md."""


class ReportError(StockroomError):
    """A report that cannot be written or read (exports.md)."""
