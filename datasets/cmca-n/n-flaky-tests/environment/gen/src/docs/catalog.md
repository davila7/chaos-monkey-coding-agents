# Catalog

## 1. Item records

1.1 An item record is a JSON object:

| Field | Required | Meaning |
|---|---|---|
| `sku` | yes | three capital letters, a hyphen, four digits: `BRK-1020` |
| `name` | yes | a non-empty name; surrounding spaces are removed |
| `weight_g` | yes | unit weight in whole grams, at least 1 |
| `dims_mm` | yes | three whole lengths in millimetres, each above 0 |
| `tags` | no | lower-case words (a letter, then letters, digits or hyphens, at most 24 characters) |
| `zone` | no | the storage zone the item must go to (`bins.md` 2.3) |
| `lead_days` | no | days from order to receipt, default 14 |
| `case_qty` | no | units per case and per pallet, default 1 |

1.2 A record that breaks 1.1 raises `CatalogError`. A boolean is not a whole
number.

1.3 Tags are a set: their order in the record does not matter and a repeated
tag counts once. Wherever tags are listed they are sorted.

## 2. The catalog

2.1 A catalog holds items by sku. Adding a sku twice raises `CatalogError`, as
does looking up an unknown sku.

2.2 Iterating a catalog gives its items sorted by sku. `tagged(tag)` gives the
items that carry the tag, sorted by sku.

2.3 `Catalog.load(path)` reads a JSON file with an `items` list. A file that
cannot be read or parsed, or that has no `items` list, raises `CatalogError`.
