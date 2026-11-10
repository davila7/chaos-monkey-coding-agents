# Changelog

## 4.2.0 (2027-03-27)

- holds: an expired hold gives its bike back to the dock. 4.1.2 dropped the
  hold but left the bike out, so free bikes went down by one per expired hold.
- `tools/sched.py run` replays one job on any snapshot.
- Docs: `triage.md`.

## 4.1.2 (2027-03-24)

- rebalance: a move never puts a dock above its capacity.
- Feed files with a wrong `count` are refused.

## 4.1.1 (2027-03-19)

- compact: `RETENTION_DAYS` moved to `spokehouse/settings.py`.
- trips: durations from `end` minus `start` with offsets.

## 4.1.0 (2027-03-11)

- The store writes a snapshot of every revision to `var/snapshots`.
- holds: holds are placed from the member app feed.
