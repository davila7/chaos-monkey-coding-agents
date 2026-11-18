# spokehouse overview

spokehouse is the back office of a city bike share. It keeps one state file,
`var/state.json`, that holds the docks, the members, the open holds and the
trip batches already applied. Scheduled jobs read the file, change it and
write it back. Nothing else writes it except operators (`operations.md` 5).

## 1. Layout

| Path | What it is |
|---|---|
| `spokehouse/` | The package: the store, the jobs, fares, feeds, time helpers |
| `tools/sched.py` | The scheduler and a replay command (`operations.md` 3) |
| `tools/admin.py` | Operator corrections (`operations.md` 5) |
| `tests/` | Unit tests: `python3 -m unittest` from the root |
| `feeds/` | Every feed file a run read, under `trips/`, `holds/`, `rebalance/` |
| `var/state.json` | The current state |
| `var/snapshots/` | A copy of every revision the store wrote (`store.md` 3) |
| `logs/sched/` | Scheduler log, one file per UTC day (`operations.md` 2) |
| `logs/deploy.log` | Releases and when they went live |
| `logs/ops.log` | Operator corrections |
| `logs/audit/` | Audits of the state against the upstream books (`operations.md` 6) |

## 2. The state

Snapshot `004131-20270327T010506Z-holds.json`, one entry of each section:

```json
{
 "applied": {"T020007": "2027-03-26T01:30:00Z"},
 "docks": {"D01": {"bikes": 13, "capacity": 26}},
 "holds": {"H61201": {"dock": "D06", "member": "M1025", "until": "2027-03-27T01:32:18+00:00"}},
 "members": {"M1001": {"balance_cents": 295, "plan": "monthly", "trips": 61}},
 "meta": {"at": "2027-03-27T01:05:06Z", "job": "holds", "rev": 4131, "version": "4.1.2"}
}
```

- `docks.*.bikes` counts bikes free to take: a held bike is not counted. It is
  never above `capacity`.
- `members.*.balance_cents` goes down by the fare of each trip; `trips` counts
  trips.
- `holds` are bikes members reserved at a dock until a time (`jobs.md` 3).
- `applied` maps each trip batch the trips job applied to the time of that run
  (`jobs.md` 2.3).
- `meta` says which revision this is, which job wrote it, when, and with which
  release. The other four sections are the data; `meta` is not part of it.

## 3. Time

All times in the state file, the logs and file names are UTC (`Z`). Feeds come
from the member app and the trip system, which write local times with their
offset (`feeds.md` 2). A time is an instant: two times are compared as
instants, whatever offsets they carry. `spokehouse.timeutil.parse_ts` reads
any of them.

## 4. Jobs and schedule

| Job | When (UTC) | Reads | Rules |
|---|---|---|---|
| `trips` | every 15 minutes at :00, :15, :30, :45 | one trips batch | `jobs.md` 2 |
| `holds` | every 15 minutes at :05, :20, :35, :50 | one holds batch | `jobs.md` 3 |
| `rebalance` | every 3 hours at :03 (00:03, 03:03, ...) | one truck manifest | `jobs.md` 4 |
| `compact` | daily at 03:32 | nothing | `jobs.md` 5 |

A rebalance run waits for the truck crew to confirm the manifest, so it can
take several minutes and still be running when the next holds run starts.
