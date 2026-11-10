# Changelog

## 2.4.0 (in progress)

- `undo`, `redo` and `history` (`undo.md`), compatible with the undo and
  redo lines the scanners write.

## 2.3.1

- `log` lists lines of every `op`, including the undo and redo lines from
  firmware 5 scanners, instead of stopping at the first one.

## 2.3.0

- Bins can be retired (`status` column in `bins.csv`). Retired bins take no
  new stock and are skipped by `issue`; their stock can be moved out.
- Bins that are gone are removed from `bins.csv`.

## 2.0.0

- Journal format 2: every line records `by` and the effects on each bin,
  with the quantity before and after.
- `state.json` format 2: bins listed in pick order.
- Format 1 lines stay in the journal as they are.

## Scanner firmware

- Firmware 5: scanners write undo and redo lines (`journal.md`, section 4).
- Firmware 4: scanners write format 2 lines.
- Firmware 3 (with binkeep 1.6): receiving by the pack. The line keeps the
  number of packs in `qty` and marks it with `"uom": "pk"`.

## 1.x

- Format 1 journal lines. A count did not record the quantity it replaced.
  Bin codes were stored as typed.
