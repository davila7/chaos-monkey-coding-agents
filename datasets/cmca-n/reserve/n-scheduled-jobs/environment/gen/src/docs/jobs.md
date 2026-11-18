# Jobs

## 1. Common rules

1.1 A job is a function `run(state, batch, now)` in `spokehouse/jobs/`. It
takes the state as loaded, its batch (`None` for `compact`) and `now`, the
time the run started, and returns the new state. It does not change the state
it was given and does not touch files; the scheduler loads and saves
(`operations.md` 2, `store.md`).

1.2 A batch that cannot be read, or a record that names an unknown member or
dock, makes the job raise `FeedError`. Nothing of that batch is applied; the
run ends with exit status 1 and writes nothing (`feeds.md` 3).

1.3 The result of a run depends only on the state it was given, its batch and
`now`.

## 2. trips

2.1 For each trip of the batch: one bike leaves the `from` dock and one arrives
at the `to` dock, the member's `trips` goes up by one, and the fare
(`fares.md`) is taken from `balance_cents`. The duration of a trip is `end`
minus `start`, in whole seconds.

2.2 Then the batch id goes into `applied` with `now`.

2.3 The trip system may deliver a batch again, up to 36 hours after its first
delivery. A batch whose id is in `applied` is not applied again: the state is
returned unchanged. That is why `applied` keeps every batch id for
`RETENTION_DAYS` (2 days, `spokehouse/settings.py`) after the run that applied
it (section 5).

## 3. holds

3.1 First, every hold whose `until` is at or before `now` expires: it leaves
`holds`, and its bike goes back to the dock (`bikes` plus one, never above
`capacity`). Holds are looked at in order of their id.

3.2 Then each record of the batch places a hold: if the dock has a free bike
and the hold id is new, `bikes` goes down by one and the hold is stored with
the `until` the record gives, as written. Otherwise the record is skipped.

3.3 `until` is written by the member app in local time with its offset
(`feeds.md` 2). Expiry compares instants (`overview.md` 3).

## 4. rebalance

For each move of the manifest, in order: the number of bikes moved is the
smallest of the manifest's `bikes`, the bikes at `from`, and the free places
at `to` (`capacity` minus `bikes`). A move of zero bikes changes nothing.

## 5. compact

`compact` removes from `applied` every batch applied more than
`RETENTION_DAYS` days before `now`: an entry stays when its time is at or
after `now` minus `RETENTION_DAYS` days. Nothing else changes.
