# rotate (release 1.5)

    python -m logkeep [--data DIR] [--now TIME] rotate [--dry-run] [--force] [STREAM ...]

`rotate` moves the content of active logs that are due into new archives,
renames and compresses archives, removes the ones the policy no longer
keeps, and updates `state.json`. The command time (`--now`) is the only
time it uses besides the times in the data.

## 1. Streams

A stream exists when it has an active log (`logs/NAME.log`) or a
`[stream NAME]` section in `policy.ini`. Archives alone do not make a
stream.

Without a `STREAM` argument `rotate` processes every stream. With
arguments it processes the streams named, each once. Streams are always
processed and printed in name order (code point order of the names).

## 2. Archives

The archives of stream `NAME` are the files in `logs/` named as below, in
the form its `naming` setting selects:

| `naming` | Plain | Compressed |
|---|---|---|
| `numbered` | `NAME.log.N` | `NAME.log.N.gz` |
| `dated` | `NAME.log.DAY` or `NAME.log.DAY.K` | the same followed by `.gz` |

`N` is a whole number from 1, `K` a whole number from 2, both written
without leading zeros. `DAY` is a calendar day written `YYYY-MM-DD`; a day
that does not exist (`2026-02-30`) does not make an archive. Files of the
other form, and every other file in `logs/`, are not archives of the stream:
`rotate` never reads, counts, renames or removes them.

Archives have an age order, from the newest to the oldest:

- numbered: by `N`, `1` is the newest;
- dated: by `DAY`, then by `K` (the archive without `K` counts as `K` = 1);
  a later day, or the same day with a higher `K`, is newer.

Whether an archive is compressed plays no part in the order. Two archives
of one stream in the same place (`web.log.3` and `web.log.3.gz`) are a data
error with the code `archives`.

The *position* of an archive is its place in the age order, 1 for the
newest.

## 3. Whether a stream is rotated

The first rule that applies decides:

1. No active log: the stream is not rotated (`no log`).
2. The active log is empty, 0 bytes: not rotated (`empty`), even with
   `--force`.
3. `--force` was given: rotated (`forced`).
4. `max_size` is not `off` and the size of the active log in bytes is at
   least `max_size`: rotated (`size`).
5. `max_age` is not `off`, the age of the active log is known and it is at
   least `max_age`: rotated (`age`).
6. Otherwise not rotated (`not due`).

The age of the active log is the command time minus the time the log was
opened. That time is the stream's `opened` in `state.json`. When the stream
has no entry there, or its entry has no `opened`, it is the time at the
start of the first line of the active log: the text before the first space,
when that text is an ISO 8601 time with `Z` or an offset. Otherwise the age
is not known.

## 4. Rotating a stream

The active log becomes a new archive, and a new, empty active log takes its
place.

- numbered: the new archive takes position 1 and every other archive moves
  one place older (section 6 gives the names).
- dated: the new archive's `DAY` is the day of the command time at the
  stream's `offset`. When the stream has no archive of that day, the name
  has no `K`; otherwise `K` is one more than the highest `K` among the
  stream's archives of that day, plain or compressed.

The new archive is made at the command time.

## 5. Retention

Retention runs for every stream processed, rotated or not, over all its
archives including a new one. Positions are counted over all of them before
anything is removed. An archive is removed when

- its position is greater than `keep`, or
- `keep_days` is not `off`, the archive has a time in `state.json`
  (`archives`), and that time is `keep_days` × 24 hours or more before the
  command time.

An archive with no time in `state.json` is removed only by its position;
the day in a dated name is not its time.

## 6. Names and compression after the run

The archives that remain are counted again in age order, from 1.

- The first `compress_after` of them keep their form. Each of the others
  that is plain is compressed: its content is replaced by the gzip
  compression of the same bytes and `.gz` is added to its name. A
  compressed archive is never decompressed. With `compress_after` = 0 a new
  archive is compressed at once.
- numbered: the archives are renamed `NAME.log.1`, `NAME.log.2`, and so on
  in age order, with no gaps, each keeping `.gz` when compressed.
- dated: an archive keeps its `DAY` and `K`.

## 7. state.json

Unless it is a dry run, `rotate` writes `state.json` (creating it when
missing). The entry of each stream processed becomes an object with:

- `opened`: the command time if the stream was rotated, else the value it
  had, as it was; left out when there was none;
- `rotations`: the value it had (0 when missing), plus 1 if the stream was
  rotated;
- `archives`: for each archive that remains and has a time, its name after
  the run and its time. The new archive's time is the command time; other
  times are copied as they were.

Nothing else is kept in the entry. The entries of streams not processed
are not changed. Times `rotate` writes are in the form of `data.md`,
section 2.

## 8. Output

For each stream processed, a line `NAME: WHAT`, where `WHAT` is
`rotate (forced)`, `rotate (size)`, `rotate (age)`, `not due`, `empty` or
`no log` (section 3). Then, indented by two spaces, one line for each
archive that remains, in age order, newest first:

- `new NAME` for the new archive, under its name after the run;
- `NEW <- OLD` when the archive's name changes (renamed or compressed);
- `NAME` when it does not change.

Then one line `remove OLD` for each archive removed, in age order, newest
first, under its name before the run.

The last line is `R rotated, X removed, C compressed`: the streams rotated,
the archives removed and the archives compressed by this command. With
`--dry-run` the output is the same, followed by `dry run: nothing written`,
and no file is written.

Example, with `[stream pay]` set to `naming = numbered`,
`compress_after = 1`, `keep = 3` and `max_size = 4K`, and a 5,000 byte
`pay.log`:

    $ python -m logkeep --now 2026-11-02T03:10:00Z rotate pay
    pay: rotate (size)
      new pay.log.1
      pay.log.2.gz <- pay.log.1
      pay.log.3.gz <- pay.log.2.gz
      remove pay.log.5.gz
      remove pay.log.6.gz
    1 rotated, 2 removed, 1 compressed

(Before the run the stream had `pay.log.1`, `pay.log.2.gz`, `pay.log.5.gz`
and `pay.log.6.gz`.)

## 9. Errors

`rotate` checks, in this order, and stops at the first error with nothing
written:

1. the command line: an unknown option is `usage`, a malformed stream name
   `bad-stream`;
2. `policy.ini` (`policy.md`, section 4): code `policy`;
3. `state.json`: a file that is not valid JSON or not format 2, an entry
   that is not an object, or, in the entry of any stream that exists
   (section 1), an `opened` or archive time that is not a time of `data.md`,
   section 2, an `archives` that is not an object, or a `rotations` that
   is not a whole number: code `state`;
4. a stream named on the command line that does not exist: refused with
   `unknown-stream`;
5. archives in the same place (section 2): code `archives`.
