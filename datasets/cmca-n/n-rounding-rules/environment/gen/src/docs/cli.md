# meterbill command line

    python -m meterbill [--tariffs FILE] COMMAND ...

`--tariffs FILE` replaces the tariff book shipped in `meterbill/data/tariffs.json`.

| Command | Output |
|---|---|
| `bill ACCOUNT [--format text\|csv\|json]` | the bill of one account file |
| `batch DIR [--format text\|csv] [--workers N]` | one line per account file in `DIR`, sorted by file name, then the payable sum per currency; bills are computed on a pool of `N` threads (default 4) |
| `quote TARIFF KWH DAYS [--format text\|json]` | what `KWH` over `DAYS` days would cost, with one standing charge segment |
| `tariffs` | the tariff book |

Errors go to standard error as `meterbill: error: <message>` with exit
status 2; argparse usage errors keep argparse's own text and status.

## Figures

- Band charges: kWh in the band times the band price, to the cent.
- Standing charge: days times the daily rate per segment; see
  `standing.prorate` for how the parts are made to add up.
- VAT: on the subtotal (energy plus standing charge).
- Credits: amounts from the old customer system, settled as it settled them.
- Payable: the total in the coins the currency uses (`cash` in the tariff
  book: `none`, `whole`, or a step such as `0.05`).
- Average per day, effective price per kWh, use per day and energy share
  are informational and written with fixed places.

## Account files

```json
{
  "account": "A-1001",
  "name": "Harbour Lane 4",
  "tariff": "home-2",
  "period": {"start": "2026-03-01", "end": "2026-03-31"},
  "readings": [{"meter": "M-1", "kwh": "182.4"}],
  "standing": [{"from": "2026-03-01", "to": "2026-03-31", "rate": "0.4110"}],
  "credits": [{"ref": "CR-77", "amount": -4.25, "note": "goodwill"}]
}
```

`standing` is optional (one segment over the period at the tariff's rate).
Decimal fields are strings; credit amounts are JSON numbers, as the old
system exports them.
