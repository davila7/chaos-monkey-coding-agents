# Shipment summary format

Write one JSON object to `/app/out/summary.json`:

```json
{
  "warehouses": {
    "<warehouse>": {"shipments": 0, "total_kg": 0.0}
  },
  "by_month": {"YYYY-MM": 0}
}
```

- `<warehouse>` is the export file name without extension (`east`, `west`, `north`).
- Count only delivered shipments. Rows whose status is cancelled or returned are excluded everywhere, in any letter case.
- `total_kg` is the summed weight in kilograms, rounded to 2 decimals. 1 lb = 0.45359237 kg.
- `by_month` counts delivered shipments from all warehouses by the month they were shipped, keys sorted ascending.

## Export formats

- `east.csv`: comma separated, `shipped` as `YYYY-MM-DD`, weight in kilograms.
- `west.csv`: semicolon separated, `shipped` as `DD.MM.YYYY`, weight in pounds with a decimal comma.
- `north.jsonl`: one JSON object per line, `shipped_at` as an ISO 8601 timestamp in UTC, weight in grams.
