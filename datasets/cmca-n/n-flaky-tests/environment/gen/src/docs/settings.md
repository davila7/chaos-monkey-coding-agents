# Settings

## 1. The settings table

1.1 Settings are a dict. Top-level keys hold a value or a section (a dict of
named values):

| Key | Default | Meaning |
|---|---|---|
| `site` | `"main"` | the site the reports describe |
| `weight_unit` | `"kg"` | unit in which weights are shown: `g`, `kg`, `lb`, `oz` |
| `length_unit` | `"cm"` | unit in which lengths are shown: `mm`, `cm`, `m`, `in` |
| `rounding.weight` | `3` | decimal places of a shown weight |
| `rounding.length` | `1` | decimal places of a shown length |
| `rounding.money` | `2` | decimal places of a shown amount |
| `reorder.safety_days` | `7` | days of demand kept as safety stock (`stock.md` 5) |
| `reorder.demand_days` | `28` | days over which demand is averaged |
| `reorder.review_day` | `None` | fixed day of the month for reviews (`stock.md` 6) |
| `putaway.origin` | `"A-01-1"` | the bin walking costs are measured from (`bins.md` 3) |
| `putaway.max_fill` | `0.9` | share of a bin's volume a pallet may fill |

1.2 `stockroom.settings.DEFAULTS` holds the built-in values. It is part of the
package and nothing may change it at run time.

## 2. Overrides

2.1 `resolve(overrides)` returns the settings to use: the built-in values with
the overrides applied. `resolve()` and `resolve(None)` return the built-in
values.

2.2 An override of a top-level value replaces it. An override of a section is
a dict whose keys replace the named keys of that section; the keys it does
not name keep their built-in values. `resolve({"rounding": {"weight": 1}})`
gives `{"weight": 1, "length": 1, "money": 2}` for `rounding`.

2.3 Overrides apply to the returned settings only. Every call of `resolve`
starts from the built-in values, so an override never shows in the result of
another call, and the returned settings, sections included, belong to the
caller: changing them changes nothing else.

2.4 Unknown keys, unknown section keys, a section given as a plain value and
values outside the ranges below raise `SettingsError`, and nothing is applied:

- units: one of the units listed in 1.1;
- `rounding.*`: a whole number from 0 to 6;
- `reorder.safety_days`, `reorder.demand_days`: a whole number of at least 0
  (`demand_days` must be at least 1 where it is used);
- `reorder.review_day`: `None` or a day of the month from 1 to 31;
- `putaway.max_fill`: above 0 and at most 1;
- `site`: a non-empty string.

2.5 `describe(settings)` lists one line per setting, `key = value` with the
value as Python writes it, sections flattened as `section.key`, sorted by the
flattened key.

## 3. Units

3.1 Weights are kept in grams and lengths in millimetres. The factors are
exact: 1 lb = 453.59237 g, 1 oz = 28.349523125 g, 1 in = 25.4 mm.

3.2 A conversion multiplies by the exact factor and rounds once, at the end,
to the requested number of places, half to even. It never rounds the value
it starts from.

3.3 `format_weight(grams, settings)` shows the weight in `weight_unit` with
`rounding.weight` places, a space and the unit: `1.250 kg`. `format_dims`
shows three lengths joined by ` x ` with the unit once at the end.

3.4 `to_grams(value, unit)` gives whole grams, rounded half to even.
