# tally command line

    python -m tally report [options] INPUT...
    python -m tally formats
    python -m tally digest [-c CURRENCY] [--locale LOCALE] INPUT...

## Inputs

CSV, TSV or JSON Lines exports, optionally gzip-compressed whatever the file
name says. Delimited files have one header row, optionally preceded by comment
lines starting with `#`; header names are matched loosely (`Qty`, `quantity`
and `units` are the same column). Rows that cannot be read are skipped with a
warning.

## report options

| Option | Meaning |
|---|---|
| `-f, --format NAME` | output format, an alias, or `all` (every format in registration order, each after a `==> name <==` line) |
| `-g, --group-by DIMS` | comma-separated dimensions: region, store, product, category, channel, currency; empty for none |
| `-m, --metrics NAMES` | comma-separated metrics: units, lines, revenue, net, discount, avg_price, discount_rate, median_units, p90_net, stores |
| `-p, --period P` | add a period column: week, month, quarter, year |
| `-c, --currency CODE` | report currency; the process currency (EUR unless `set_currency()` changed it) when not given |
| `--top N`, `--top-by METRIC` | add a top-N products section |
| `--compare P` | add a period-over-period section |
| `--pivot ROWS:COLS` | add a cross table of two dimensions |
| `--mix` | add a channel mix section |
| `--forecast N` | add an N-period trend projection |
| `--sources` | add a per-file section |
| `--title TEXT` | report title |
| `--locale L` | locale for output: en, en-GB, de, fr, es, it, nl, sv, ja |
| `--input-locale L` | locale of numbers and dates in the inputs (en when not given) |
| `--since YYYY-MM`, `--until YYYY-MM` | months to keep, inclusive |
| `-w, --width N` | width for text formats; from `COLUMNS` when not given |
| `--config FILE` | option values from the `[report]` table of an INI file; options on the command line win |
| `--no-check` | skip plausibility checks |
| `--strict` | exit with status 3 if any row was skipped or flagged |
| `--list-formats` | list formats and exit |

`python -m tally formats` is the same as `report --list-formats`.

## Output streams and exit status

The report goes to stdout. Warnings, errors and the count of skipped rows go to
stderr through the `logging` module, one line per message in the form
`<logger name>: <LEVEL>: <message>`.

| Status | Meaning |
|---|---|
| 0 | report written |
| 2 | usage error or invalid options |
| 3 | `--strict` and at least one warning |
| 4 | an input or the config file could not be read, or an option value was rejected |

## Reproducible output

Footers carry a timestamp. Set `SOURCE_DATE_EPOCH` (seconds since 1970) to fix
it, and `COLUMNS` (or `--width`) to fix the width of text formats.
