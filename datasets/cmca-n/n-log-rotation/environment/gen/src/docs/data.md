# Data files

## 1. The data directory

| Path | What it holds |
|---|---|
| `policy.ini` | the rotation and retention policy (`policy.md`) |
| `state.json` | what logkeep remembers about each stream (section 5) |
| `logs/` | active logs, archives and anything else people leave there (section 4) |

## 2. Times

logkeep writes times as `YYYY-MM-DDTHH:MM:SSZ`, in UTC (`dates.stamp`).

Lines written by the parts of the service start with an ISO 8601 time with
`Z` or an offset, sometimes with fractions of a second, for example
`2026-11-01T22:04:17.250+01:00`. The parts of the service run with
different offsets, so the text of two times does not say which is earlier.

Release 1.2 wrote the times in `state.json` as `YYYY-MM-DD HH:MM:SS`,
without an offset; these are UTC. Entries it wrote are still in the file
and are read as UTC. Every other time in `state.json` has `Z` or an offset.

Times are always compared as instants.

## 3. Stream names

A stream name is a lower case letter followed by lower case letters,
digits, `_` or `-` (`streams.NAME`). Anything else is not a stream name.

## 4. logs/

The active log of stream `NAME` is `logs/NAME.log`. Its parts append lines
to it; each line normally starts with a time (section 2), but some parts
start a new log with a banner line that does not. Log lines are UTF-8 text
and many hold names and addresses outside ASCII.

Archives sit next to the active log; their names are given in `rotate.md`,
section 2. People also leave other files in `logs/`: copies made by hand
(`web.log.bak`), unfinished copies (`web.log.1.tmp`), notes. They are not
archives, whatever their names start with.

## 5. state.json

    {
      "format": 2,
      "streams": {
        "web": {
          "opened": "2026-11-01T00:00:04Z",
          "rotations": 211,
          "archives": {
            "web.log.1": "2026-11-01T00:00:04Z",
            "web.log.2.gz": "2026-10-31T00:00:03Z"
          }
        }
      }
    }

`format` is 2. `streams` maps a stream name to an object with:

| Key | Meaning |
|---|---|
| `opened` | when the current active log was started (the last rotation) |
| `rotations` | how many times the stream has been rotated, a whole number |
| `archives` | for each archive, by file name, the time it was made |

Any of the three keys can be missing: the old cron script did not record
every stream, a stream that was never rotated by logkeep has no `opened`,
and archives copied in by hand from the old server have no time. A missing
`state.json` is the same as one with no entries. `state.save` writes the
file.
