# Data files

All files live in the data directory (`--data`).

## 1. items.csv

Columns `sku`, `description`, `pack_size`. `sku` is unique and compared
exactly, case included. `pack_size` is the number of units in one pack, at
least 1. Quantities everywhere else in binkeep are in units.

## 2. bins.csv

Columns `bin`, `zone`, `pick_seq`, `status`.

- `bin` is the bin code, for example `C-04`. Codes are compared after
  trimming spaces and turning letters to upper case, so ` c-04` names the same
  bin as `C-04`. binkeep always writes the normalized form.
- `pick_seq` is the position of the bin on the picking walk. Bins are listed
  and picked in `pick_seq` order, lowest first, then by code. It is not the
  order of the codes.
- `status` is `active` or `retired`. A retired bin is being taken out of
  use: it may still hold stock, and that stock can be moved out of it or
  corrected down with `fix`, but no operation may add stock to it (code
  `retired-bin`). `issue` does not pick from retired bins and `count` does
  not count them.
- A bin that is gone from the building is removed from `bins.csv`. A bin
  code that is not in the file is unknown (code `unknown-bin`), even when
  old journal lines name it.

## 3. state.json

The current stock:

    {
      "format": 2,
      "stock": {
        "BX-1042": {"C-04": 12, "A-02": 3}
      }
    }

- Items are sorted by SKU. The bins of an item are in pick order
  (`pick_seq`, then code). A bin with quantity 0 is left out, and so is an
  item with no stock.
- Every bin in the file is in `bins.csv`.
- Two-space indentation, a newline at the end.

`state.json` is always the stock that the journal leads to. binkeep writes
it from `Store.to_json()`.
