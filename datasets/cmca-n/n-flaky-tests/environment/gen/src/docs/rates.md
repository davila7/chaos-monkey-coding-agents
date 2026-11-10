# Carrier rates

## 1. Rate tables

1.1 A carrier publishes a rate table per service as a JSON object:

| Field | Meaning |
|---|---|
| `carrier`, `service` | names, as the carrier writes them |
| `effective` | first day the table applies, `YYYY-MM-DD` |
| `currency` | currency code of every amount |
| `bands` | list of `{"up_to_kg": n, "cents": c}`, `up_to_kg` rising |
| `over_per_kg_cents` | price of each kilogram above the last band (default 0) |
| `zones` | factor per destination zone, as strings: `{"1": "1.00", "2": "1.18"}` |
| `fuel_pct` | fuel surcharge in percent (default 0) |

1.2 A table that breaks 1.1 raises `RateError`: a missing field, no band, bands
that do not rise, a band with a weight of 0 or less or a negative price, no
zone, a factor or surcharge that is not a number of at least 0, a bad date.

1.3 Carriers reissue tables without changing `carrier`, `service` or
`effective`: a surcharge or a zone can change while the table keeps its
effective date. Two tables are the same table only when they are equal as
JSON values.

## 2. Billable weight

2.1 The billable weight of a parcel is the larger of its actual weight and
its volume weight (length x width x height in cubic centimetres divided by
5000), rounded up to a whole kilogram, and at least 1 kg.

2.2 A weight of 0 or less raises `RateError`.

## 3. Quotes

3.1 `quote(spec, weight_g, zone, dims_mm=None)` prices one parcel in cents:

1. take the price of the first band whose `up_to_kg` is at least the billable
   weight; above the last band, the last band's price plus
   `over_per_kg_cents` for each kilogram above it;
2. multiply by the zone factor and by `1 + fuel_pct / 100`;
3. round half to even to a whole cent, once, at the end.

3.2 A zone the table does not list raises `RateError`.

3.3 `format_cents(cents, currency)` writes `12.34 EUR`; a negative amount
gets a leading minus sign.

## 4. The table cache

4.1 Parsing a table is slow for large tables, so `table(spec)` keeps the
tables it has parsed for the life of the process. It parses a spec only when
it has not parsed an equal one before; otherwise it returns the table it
already has. `quote` uses `table`.

4.2 Specs are compared as JSON values (1.3): two specs with the same content
share one parsed table even when they are different objects or list their
keys in another order; specs that differ anywhere, in a band, a zone or the
surcharge, get their own tables. A spec that is changed after it was used is
compared by its new content when it is used again.

4.3 `cache_stats()` returns `{"tables": n, "hits": h, "misses": m}`: the
number of parsed tables held, the calls of `table` that found one, and the
calls that had to parse. `clear_cache()` drops every table and sets both
counters to 0.

4.4 A spec that is not plain JSON (a value that `json` cannot write) raises
`RateError`.
