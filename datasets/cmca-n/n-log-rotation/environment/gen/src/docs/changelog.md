# Changelog

## 1.5 (in progress)

- `rotate` (`rotate.md`). The cron script on the old server is retired.

## 1.4

- `archives` lists every file next to an active log.
- `policy.ini` lowered `compress_after` for some streams. Archives the cron
  script left plain under the old values are still plain; the new values
  apply from the next `rotate`.
- Archives of a few streams were copied by hand from the old server. They
  have no time in `state.json`.

## 1.3

- Some streams moved from numbered to dated archive names. Their numbered
  archives were left in `logs/` for the auditors and must stay as they are.
- `state.json` times are written with `Z`.

## 1.2

- `state.json` format 2. Times were written as `YYYY-MM-DD HH:MM:SS` in
  UTC; entries from that release are still in the file.
