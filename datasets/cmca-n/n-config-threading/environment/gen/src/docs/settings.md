# quoter settings

quoter prices parcel shipments between European and overseas addresses with
four carriers. Every price depends on settings: which rate card, which
carriers, which currency, how to round, and so on. This page lists every
setting, where values come from, and what each one changes.

## Where values come from

In increasing priority:

1. The fallback value of each field of `quoter.settings.Settings`.
2. The `[quoter]` table of an INI file given with `--config PATH` or the
   `QUOTER_CONFIG` environment variable.
3. `QUOTER_<NAME>` environment variables, for example `QUOTER_TAX_RATE=0.19`.
   Variables whose name is not a setting are ignored.
4. `--set NAME=VALUE` on the command line (repeatable; the last one wins).
5. The global options `--currency` (upper-cased), `--units`, `--width`
   (sets `line_width`), `--debug` and `--no-cache` (sets `cache_enabled` to
   false).

Values are text until `parse_value` converts them to the type of the field.
A value of the wrong form, an unknown name, or a value outside the choices
listed below stops the command with exit status 2 before anything is quoted.
Some settings hold a small format of their own (`zone_overrides`,
`discount_tiers`); those are read when they are first needed, and a mistake in
them is reported then, with exit status 1.

## Settings

Where this table and the command line disagree, the command line is the
reference.

| Name | Type | Fallback | Meaning |
|---|---|---|---|
| `currency` | text | `EUR` | Currency of the `gross_local` amount of every quote. Prices are computed in EUR and converted at the end. |
| `rounding` | choice | `half_up` | How `round_money` rounds: `half_up`, `half_even` or `up`. |
| `round_step` | decimal | `0.01` | The step `round_money` rounds to: `0.05` rounds to five cents. Must be above zero. |
| `tax_rate` | decimal | `0.20` | Value added tax rate for destinations that charge VAT. |
| `fuel_pct` | decimal | `12.5` | Fuel surcharge in percent. Each carrier passes on its own share of it. |
| `dim_divisor` | integer | `5000` | Volumetric weight is length x width x height in cm divided by this. Must be above zero. |
| `units` | choice | `metric` | Units of weights and dimensions given as input: `metric` (kg, cm) or `imperial` (lb, in). Pricing always works in kg and cm. |
| `carriers` | list | `ground,express,freight,courier` | Enabled carriers, in the order they are tried and listed. Names must be known carriers. |
| `zone_overrides` | text | empty | `CC=Z,...`: the price zone for destination country `CC` from any other country. |
| `rate_card` | choice | `standard` | Base rate card: `standard` or `2026`. |
| `surcharge_remote` | decimal | `4.50` | Surcharge for remote destination postcodes. |
| `surcharge_oversize` | decimal | `12.00` | Surcharge when the longest side of the shipped box is above 120 cm. |
| `surcharge_residential` | decimal | `2.10` | Surcharge for residential delivery. |
| `surcharge_peak` | decimal | `0` | Surcharge in peak season (15 November to 31 December); zero turns it off. |
| `insurance_pct` | decimal | `1.2` | Insurance premium in percent of the declared value. |
| `insurance_min` | decimal | `3.00` | Smallest insurance premium. |
| `discount_tiers` | text | `10:2,50:5,200:8` | Volume discount for batches: `COUNT:PERCENT,...`. |
| `fx_margin` | decimal | `1.5` | Margin in percent added to the reference exchange rate. EUR has none. |
| `box_set` | choice | `standard` | Box catalogue: `standard`, `eco` or `none` (ship as given). |
| `packing_margin_cm` | integer | `2` | Space left on every side of an item inside a box. |
| `cache_enabled` | boolean | true | Keep quote results for reuse. |
| `debug` | boolean | false | Trace pricing calls and print cache statistics to stderr. |
| `line_width` | integer | `72` | Width text tables and labels are cut or drawn to. Must be above zero. |
| `csv_delimiter` | text | `,` | Field delimiter of CSV output. |
| `json_indent` | integer | `2` | Indentation of JSON output; `0` writes one line. |
| `label_format` | choice | `short` | Label preview: `short` or `long` (adds zone, box, delivery date, surcharges). |
| `pricing_date` | date | `2026-01-05` | The day quotes are made: decides peak season and delivery dates. |
| `saturday_delivery` | boolean | false | Count Saturdays as delivery days. |
| `ground_markup` | decimal | `0` | Markup in percent for the ground carrier. |
| `express_markup` | decimal | `4` | Markup in percent for the express carrier. |
| `freight_markup` | decimal | `2.5` | Markup in percent for the freight carrier. |
| `courier_markup` | decimal | `6` | Markup in percent for the courier. |

Booleans accept `1`, `0`, `true`, `false`, `yes`, `no`, `on` and `off`.

## Tracing

`--debug` (or `debug = true`) writes one `trace:` line to stderr for every
priced carrier service, showing the carrier and service and the result, and a
`cache:` line with the number of stored results and of reuses at the end of
the command. `QUOTER_TRACE=1` in the environment turns on the `trace:` lines
alone.

## How a quote is priced

For each enabled carrier and each of its services:

1. The item is put in the smallest box of the catalogue it fits, if any; the
   box tare is added to the weight.
2. Chargeable weight: the greater of the actual and the volumetric weight,
   rounded up to 0.1 kg.
3. The carrier must accept the weight and the longest side.
4. Base price from the rate card by zone and weight band, times the service
   multiplier, then the carrier's own adjustment; rounded to cents.
5. Markup, surcharges, fuel on base plus markup plus surcharges, insurance.
6. Net: the sum, rounded with `rounding` and `round_step`.
7. Gross: net plus tax for the destination.
8. `gross_local`: gross converted to `currency` and rounded like net.

Quotes are sorted by gross, then delivery date, carrier and service.

A batch takes the cheapest quote of each row. Its total applies the volume
discount to the sum of the net prices and adds tax at `tax_rate`.
