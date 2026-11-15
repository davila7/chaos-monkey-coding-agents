# Commands

All commands take the global options of `overview.md`, section 2. Output
goes to standard output, one line per item, and errors follow
`overview.md`, section 4.

## 1. status

    status

One line per active log (`data.md`, section 4), in name order:
`NAME  SIZE  OPENED`, separated by two spaces. `SIZE` is the size of the
file in bytes. `OPENED` is the stream's `opened` value in `state.json`
exactly as stored, or `-` when there is none.

## 2. write

    write STREAM TEXT

Appends one line, `TIME TEXT` followed by a newline, to the stream's active
log, where `TIME` is the command time in the form logkeep writes
(`data.md`, section 2). The log and the `logs` directory are created when
missing. A malformed stream name is `bad-stream`; a `TEXT` that holds a
line break is `bad-text`. `write` prints nothing and does not touch
`state.json`.

## 3. archives

    archives STREAM

Prints every file in `logs/` whose name starts with `STREAM.log.`, sorted
by name, as `NAME  SIZE`. This lists whatever lies next to the active log,
including files that are not archives (`data.md`, section 4). When there is
no such file and no active log, the command is refused with
`unknown-stream`.

## 4. rotate

Release 1.5, see `rotate.md`.
