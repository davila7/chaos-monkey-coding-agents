# Commands

    python -m binkeep [--data DIR] [--by NAME] receive SKU BIN QTY [--packs]
    python -m binkeep [--data DIR] [--by NAME] issue SKU QTY
    python -m binkeep [--data DIR] [--by NAME] move SKU FROM TO QTY
    python -m binkeep [--data DIR] [--by NAME] count SKU BIN QTY
    python -m binkeep [--data DIR] [--by NAME] fix SKU BIN QTY
    python -m binkeep [--data DIR] stock [SKU]
    python -m binkeep [--data DIR] log [--limit N]

Release 2.4 adds `undo`, `redo` and `history` (`undo.md`).

## 1. Arguments

- `QTY` and `N` are whole numbers written in decimal. `QTY` is at least 1,
  except for `count` and `fix`, where 0 is allowed. `N` is at least 1.
  Anything else is a usage error.
- `SKU` must be in `items.csv` (code `unknown-sku`).
- Bin codes are normalized (`data.md`, section 2) and must be in `bins.csv`
  (code `unknown-bin`).

## 2. Stock operations

Each operation that succeeds appends one format 2 line (`journal.md`,
section 1) with the next `seq`, the `--by` name and its effects, and writes
`state.json`.

- `receive SKU BIN QTY` adds `QTY` units to the bin; with `--packs`, `QTY`
  packs of the item's `pack_size` units. The bin must be active
  (`retired-bin`).
- `issue SKU QTY` takes `QTY` units out of the active bins that hold the
  item, in pick order, emptying each bin before going to the next. If the
  active bins hold fewer than `QTY` units in total, nothing is taken (code
  `short`).
- `move SKU FROM TO QTY` takes `QTY` units out of `FROM`, which may be
  retired, and adds them to `TO`, which must be active (`retired-bin`).
  `FROM` must hold at least `QTY` units (`short`). The effects list `FROM`,
  then `TO`.
- `count SKU BIN QTY` records a cycle count: the bin's quantity becomes
  `QTY`. The bin must be active (`retired-bin`). A count that finds the expected quantity is
  still journaled, with equal `before` and `after`.
- `fix SKU BIN QTY` is a correction by hand, for example after damage is
  found: the quantity becomes `QTY`. Any bin may be fixed, but a retired bin
  cannot be fixed upwards (`retired-bin`).

Checks run in this order: arguments, item, bins (for `move`, `FROM` then
`TO`, then `same-bin`), quantities, bin status.

## 3. Output

An operation prints its journal line as text: a heading `#<seq> <op> <sku>`
and one line per effect, two spaces, the bin, the quantity before, `->`, the
quantity after:

    #118 move BX-1042
      C-04 12 -> 4
      A-02 3 -> 11

`stock` prints one line per item and bin, items by SKU, bins in pick order:
the SKU left-aligned in 10 characters, two spaces, the bin left-aligned in
6, two spaces, the quantity right-aligned in 6. With `SKU`, only that item.

`log` prints the latest `N` journal lines (default 10), oldest first: the
`seq` right-aligned in 5 characters, two spaces, the `op` left-aligned in 7,
two spaces, the SKU. Every line of the journal is listed, whatever its
format or `op`.
