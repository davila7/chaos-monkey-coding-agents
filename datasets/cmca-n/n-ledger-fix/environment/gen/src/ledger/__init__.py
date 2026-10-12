"""Multi-currency statement ledger.

The package reads bank and card statements (``ledger.parse``), books their
entries (``ledger.book``), converts them into US dollars (``ledger.fx``) and
builds reports (``ledger.report``) that ``ledger.render`` turns into text, CSV,
Markdown or JSON. ``docs/conventions.md`` is the reference for every rule.
"""

__version__ = "3.4.0"

BASE_CURRENCY = "USD"

__all__ = ["BASE_CURRENCY", "__version__"]
