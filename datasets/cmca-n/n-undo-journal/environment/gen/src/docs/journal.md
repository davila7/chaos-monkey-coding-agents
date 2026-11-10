# The journal

`journal.jsonl` holds one JSON object per line, oldest first. Every line has
an integer `seq`, unique and increasing through the file, and an `op`. A new
line takes the highest `seq` in the file plus one. Empty lines are skipped.

Two formats are in the file. A line with `"v": 2` is format 2; a line
without `v` is format 1.

## 1. Format 2

Written by binkeep 2.x and by the scanners since firmware 4:

    {"v":2,"seq":118,"op":"move","by":"dock-2","sku":"BX-1042","effects":[{"bin":"C-04","before":12,"after":4},{"bin":"A-02","before":3,"after":11}]}

- Keys in this order: `v`, `seq`, `op`, `by`, `sku`, then `target` for undo
  and redo lines (section 4), then `effects`.
- `effects` lists every bin the line changed, in the order the changes were
  made, with the quantity before and after. Bin codes are normalized.
- binkeep writes compact JSON (no spaces after `,` and `:`), non-ASCII
  characters as they are, one line per entry (`journal.dumps`).
- `op` is `receive`, `issue`, `move`, `count` or `fix` for a stock
  operation, or `undo` or `redo` (section 4).

## 2. Format 1

Written by binkeep 1.x and the scanners before firmware 4. These lines are
still in the journal and are never rewritten. They have no `v`, no `by` and
no `effects`; they say what was asked, not what changed:

| `op` | Fields | Meaning |
|---|---|---|
| `receive` | `sku`, `bin`, `qty`, optional `uom` | `qty` added to `bin`. With `"uom": "pk"`, `qty` counts packs, and the units added are `qty` times the item's `pack_size` |
| `issue` | `sku`, `picks` | `picks` is a list of `[bin, qty]` pairs, in the order picked; each `qty` was taken out of that bin |
| `move` | `sku`, `from`, `to`, `qty` | `qty` taken out of `from` and added to `to` |
| `count` | `sku`, `bin`, `qty` | the bin was counted and set to `qty`; the quantity before the count was not recorded |
| `fix` | `sku`, `bin`, `qty` | the quantity was corrected by hand to `qty` |

Bin codes in format 1 lines are as the operator typed them, so they may be
in lower case or carry spaces; normalize them (`data.md`, section 2) before
use. 1.x wrote JSON with a space after `,` and `:`.

## 3. Reading

`journal.read(path)` returns the lines as dictionaries, in file order.
binkeep never needs the journal to know the stock; `state.json` holds it.
The journal is the record of what happened, and it is what `undo`, `redo`
and `history` work from (`undo.md`).

## 4. Undo and redo lines

Since firmware 5 the scanners write undo and redo lines, in format 2:

    {"v":2,"seq":131,"op":"undo","by":"night","sku":"BX-1042","target":118,"effects":[{"bin":"A-02","before":11,"after":3},{"bin":"C-04","before":4,"after":12}]}

`target` is the `seq` of the operation line that was undone or redone.
`effects` are the changes the undo or redo line itself made, in the order it
made them. What these lines mean, and the rules binkeep 2.4 follows when it
writes them, are in `undo.md`.
