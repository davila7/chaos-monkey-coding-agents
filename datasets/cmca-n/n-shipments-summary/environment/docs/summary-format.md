# Shipment summary

## Script

`/app/bin/summarize.py` is run as

    python3 /app/bin/summarize.py DATA_DIR OUT_FILE

It reads every export in `DATA_DIR`, writes the summary as JSON to `OUT_FILE`
and exits with status 0. Python 3.12 standard library only. The script is also
run on other exports from the same depots, so nothing about the current
contents of `/app/data` may be built into it.

## Output

```json
{
  "depots": {
    "<depot>": {"shipments": 0, "total_kg": 0.0}
  },
  "by_month": {"YYYY-MM": 0},
  "duplicates_resolved": 0
}
```

- `depots` has one entry per export file in `DATA_DIR`. The depot name is the
  file name without its extension. A depot with no counted shipments still has
  an entry with zeros.
- `shipments` is the number of counted shipments credited to the depot.
- `total_kg` is the sum of their weights in kilograms. Convert each weight
  exactly, add them up, and round the sum to 2 decimals.
- `by_month` maps each month that has at least one counted shipment to the
  number of counted shipments shipped in that month, over all depots. Keys are
  in ascending order.
- `duplicates_resolved` is defined in `duplicates.md`.

## Records

- Every data record in an export is one shipment. Comment lines, column
  headers, totals and trailer records are not shipments.
- A shipment id is the letters SH followed by a number. Exports format ids
  differently (prefix case, separators, zero padding). Two records refer to the
  same shipment when their numbers are equal. See `duplicates.md`.
- A shipment is counted when its status is `delivered` or `delivered_late`,
  compared without regard to case and with spaces and hyphens read as
  underscores. Every other status (cancelled, returned, held, and so on) is not
  counted.
- Each export states its weight unit and its date convention in the file
  itself: in a header comment, a column or field name, an attribute, or the
  layout it names. Conversions: 1 lb = 0.45359237 kg, 1 oz = 0.028349523125 kg,
  1 g = 0.001 kg.
- The month of a shipment is the calendar month of its ship time in UTC. A ship
  date without a time of day is already a UTC date.
- A fixed-width export names its layout on its first line, as `#LAYOUT <name>`.
  The layout is described in `/app/docs/layouts/<name>.txt`. Depots move between
  layouts from one export to the next, so the script must follow the layout the
  file names.

## Checking

`python3 /app/tools/check_summary.py` checks the shape of `/app/out/summary.json`
and that it matches what the script produces. It stops at the first problem it
finds. It does not check the values.
