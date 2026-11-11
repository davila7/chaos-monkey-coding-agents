# Undo, redo and history (release 2.4)

    python -m binkeep [--data DIR] [--by NAME] undo [--steps N]
    python -m binkeep [--data DIR] [--by NAME] redo [--steps N]
    python -m binkeep [--data DIR] history [--limit N]

`undo` reverses the latest stock operations, `redo` applies undone ones
again, `history` lists the operations and whether they are in effect. The
scanners have written undo and redo lines since firmware 5, so binkeep must
read the ones already in the journal and continue from them: an undo made
on a scanner can be redone from the command line, and the other way round.

## 1. Operations

The operations are the journal lines whose `op` is `receive`, `issue`,
`move`, `count` or `fix`, in either format. Undo and redo lines are not
operations.

## 2. The two stacks

Whether an operation is in effect is worked out from the journal alone, by
reading it from the first line to the last with two stacks, *done* and
*undone*, both empty at the start:

- An operation line is pushed onto *done*, and *undone* is emptied. The
  operations that were on *undone* can never be redone; they are *dropped*.
- An undo line takes the top of *done*, which must be the operation its
  `target` names, and pushes it onto *undone*.
- A redo line takes the top of *undone*, which must be the operation its
  `target` names, and pushes it back onto *done*.

A journal whose undo or redo lines do not match the stacks this way is
broken (`DataError`, code `journal`). The lines binkeep writes (sections 3
to 5) follow the same rules, so the stacks after a command are the stacks
read from the journal it leaves.

## 3. undo

`undo` reverses the operation on top of *done*:

- *done* is empty: refused, code `nothing-to-undo`.
- The top is a `fix`: refused, code `barrier`. A fix is a decision made by
  hand on the floor; it is never undone, and nothing older than it can be
  undone either.
- The top is a format 1 `count`: refused, code `irreversible`, since the
  quantity before the count is not known.

Otherwise the bins the operation changed get their earlier quantities back,
in the reverse of the order in which the operation changed them:

- Format 2 operation: each bin in `effects`, last first, is set to its
  `before` quantity.
- Format 1 operation: the change of each bin is worked out from the line
  (`journal.md`, section 2) and taken back, last change first. A `receive`
  takes the units it added off the bin again; an `issue` puts each pick
  back, the last pick first; a `move` takes the quantity off `to`, then puts
  it back into `from`.

## 4. Which bins can be restored

Undo and redo put back quantities the journal recorded. They do this
whatever the bin's status: a retired bin takes back the stock an undone
move took out of it. The `retired-bin` rule of the stock operations does not
apply to them.

A bin that is no longer in `bins.csv` cannot be restored: the whole step is
refused, code `unknown-bin`.

## 5. redo

`redo` applies again the operation on top of *undone* (empty: refused, code
`nothing-to-redo`). It reverses the undo line that undid that operation, the
most recent one for it: each bin in that undo line's `effects`, last first,
is set back to its `before` quantity. Section 4 applies.

## 6. Steps

`--steps N` (default 1) undoes or redoes `N` operations, one after another,
each against the stock and stacks the previous step left. The steps are all
or nothing: if any step is refused, no step is carried out, nothing is
written, and the command fails with the code of the first refused step. When
all `N` steps can be carried out, each one is written as its own line.

## 7. Lines written

Each step appends one format 2 line (`journal.md`, sections 1 and 4) with
the next `seq`, `op` `undo` or `redo`, the `--by` name, the operation's
`sku`, the operation's `seq` as `target`, and as `effects` the bins the step
set, in the order it set them, each with the quantity it had before the step
and the quantity after. A bin that ends at 0 is left out of `state.json`
(`data.md`, section 3).

## 8. Output

For each step, in order, a heading `#<seq> <op> <sku> (#<target> <operation op>)`
and its effects as in `commands.md`, section 3:

    #131 undo BX-1042 (#118 move)
      A-02 11 -> 3
      C-04 4 -> 12

A refused command prints nothing on standard output.

## 9. history

`history` lists the latest `N` operations (default 20), newest first: the
`seq` right-aligned in 5 characters, two spaces, the `op` left-aligned in 7,
two spaces, the SKU left-aligned in 10, two spaces, and the status:

| Status | Operation |
|---|---|
| `done` | on *done*, other than a fix |
| `barrier` | a fix (always on *done*) |
| `undone` | on *undone*: `redo` can apply it again |
| `dropped` | undone, and *undone* was emptied after that |

Undo and redo lines are not listed and do not count towards `N`.

## 10. Codes

| Code | Exit status | When |
|---|---|---|
| `usage` | 2 | a wrong command line, for example `--steps 0` |
| `nothing-to-undo`, `nothing-to-redo` | 3 | the stack is empty |
| `barrier` | 3 | the operation to undo is a fix |
| `irreversible` | 3 | the operation to undo is a format 1 count |
| `unknown-bin` | 3 | a bin to restore is not in `bins.csv` |
| `journal` | 4 | undo or redo lines in the journal break section 2 |
