# Shipment summary

## Script

`/app/bin/summarize.py` is run as

    python3 /app/bin/summarize.py DATA_DIR OUT_FILE

It reads every export in `DATA_DIR`, writes the summary as JSON to `OUT_FILE`
and exits with status 0. Python 3.12 standard library only. The script is also
run on other exports from the same depots (other weeks, other file counts, other
values), so nothing about the current contents of `/app/data` may be built into
it. It must finish within a few minutes on an export set of this size.

## Output

```json
{
  "depots": {
    "<depot>": {"shipments": 0, "total_kg": 0.0}
  },
  "months": {
    "YYYY-MM": {"shipments": 0, "total_kg": 0.0}
  },
  "corrections_applied": 0,
  "resends_dropped": 0,
  "handovers": 0
}
```

- `depots` has one entry per depot that has at least one export file in
  `DATA_DIR`, even when nothing is counted for it (then both values are zero).
- `shipments` is the number of counted shipments credited to the depot, and
  `total_kg` the sum of their weights in kilograms.
- `months` maps each month that has at least one counted shipment to the number
  and total weight of counted shipments shipped in that month, over all depots.
  Keys are in ascending order.
- `total_kg` values: convert each weight exactly, add them up, and round the sum
  to 2 decimals. Do not round individual weights.
- `corrections_applied`, `resends_dropped` and `handovers` are defined in
  `corrections.md` and `handovers.md`.

## Export files

- Every regular file in `DATA_DIR` is one export. Files ending in `.gz` are
  gzip-compressed exports; decompress them and read them like the others.
- The depot is the part of the file name before the first hyphen
  (`east-w12.csv` and `east-w3r.csv.gz` are both east exports). The rest of the
  name is a label for people and says nothing reliable about order. Each export
  states its sequence number inside the file; see `corrections.md`.
- Each depot has its own format, described in `depots/<depot>.md`. Files of the
  same depot can differ from each other, and conventions can change part way
  through a file. What a file declares about itself (directives, header rows,
  attributes, layout lines) applies from the point where it appears and wins
  over the depot notes, which describe the usual case.
- Text is UTF-8 unless the file starts with a byte order mark or declares
  another character set. Comment lines, directives, column headers, page
  headers, totals and trailer lines are not records.

## Records

- A shipment id is the letters SH followed by a number. Exports format ids
  differently (letter case, separators, zero padding). Two records refer to the
  same shipment when their numbers are equal.
- Records are new, correction or void records. How a depot marks the type is in
  its depot note; how the types combine is in `corrections.md`.
- A shipment is counted when its status is `delivered` or `delivered_late`,
  compared without regard to case and with spaces and hyphens read as
  underscores. Status codes are listed in the depot notes and layouts. Every
  other status (cancelled, returned, held) is not counted.
- Weights: 1 lb = 0.45359237 kg, 1 oz = 0.028349523125 kg, 1 g = 0.001 kg.
- The month of a shipment is the calendar month of its ship time in UTC. A ship
  time with a UTC offset must be converted to UTC first. A ship date without a
  time of day is already a UTC date. Other dates in a record (booking dates,
  for example) do not decide the month.

## Checking

`python3 /app/tools/check_summary.py` checks `/app/out/summary.json`: its shape,
that it matches what `/app/bin/summarize.py` writes for `/app/data`, and how many
of its values agree with the reference figures for `/app/data`. It names only
the first few values that disagree and never prints the reference figures. It
cannot tell you whether the script will be right on other exports.
