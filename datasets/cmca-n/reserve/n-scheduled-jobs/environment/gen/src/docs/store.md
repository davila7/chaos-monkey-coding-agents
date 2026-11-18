# The store

`spokehouse/store.py` reads and writes `var/state.json`.

## 1. load

`load(path)` returns the state in the file, `meta` included. The `rev` in
`meta` is the revision the state was loaded at.

## 2. save

2.1 `save(path, state, job=..., at=..., snapshots=...)` writes `state` as the
next revision: `meta.rev` one above the revision in the file, `meta.job` and
`meta.at` from the arguments, `meta.version` the release of the package.

2.2 Jobs run at the same time: a rebalance run can still be waiting for its
truck when a holds run loads and saves. A state is saved only if the file is
still at the revision that state was loaded at. If another run wrote the file
in between, `save` raises `spokehouse.errors.StaleState` and writes nothing,
neither the file nor a snapshot. The scheduler then reloads the file and runs
the job again on the new state (`operations.md` 2.3); no run may write over
the changes of another.

2.3 The file is replaced in one step (written to a temporary file in the same
directory, then renamed), so a reader never sees half a state.

## 3. Snapshots

With `snapshots` set, every revision written is also copied to that directory
as `<rev, 6 digits>-<meta.at as YYYYMMDDTHHMMSSZ>-<job>.json`, for example
`004412-20270328T111509Z-trips.json`. The scheduler always sets it to
`var/snapshots`. Snapshots are never changed after they are written.
