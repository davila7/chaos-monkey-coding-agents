# Operations

## 1. Releases

`logs/deploy.log` lists each release with the time it went live. The
scheduler is paused around a deploy, so every run uses one release from start
to end; the start line of a run names it (`version=`), and so does
`meta.version` in what it wrote.

## 2. The scheduler

2.1 For each run the scheduler loads the state when the run starts, and when
the run ends it reads the batch, calls the job with the state it loaded and
`now` (the start time), and saves the result (`store.md` 2). The log lines:

```
2027-03-27T00:03:00Z start rebalance run=r-20270327T0003 version=4.1.2 loaded=004121-20270327T000010Z-trips.json feed=feeds/rebalance/20270327T0003-M20270327T0003.jsonl
2027-03-27T00:04:35Z end rebalance run=r-20270327T0003 exit=0 wrote=004122-20270327T000435Z-rebalance.json
```

`loaded` is the snapshot of the revision the run loaded; `wrote` is the
snapshot it wrote. Runs of different jobs overlap, so lines of two runs can
interleave.

2.2 A job that raises ends the run with an `error` line and
`exit=1 wrote=-`; the run wrote nothing.

2.3 When `save` raises `StaleState`, the scheduler logs
`retry <job> run=<id> reason=stale loaded=<snapshot>`, reloads the file and
runs the job again on what it loaded, with the same batch and `now`, then
saves that. It gives up after 5 attempts.

## 3. Replaying a run

```
python3 tools/sched.py run <job> --state var/snapshots/<loaded> --now <start time> [--feed <feed>]
```

prints the state the job returns for that input, `meta` as loaded, and saves
nothing. With the `loaded`, start time and `feed` of a start line it gives the
data of the snapshot that run wrote, as long as the code is the release the
run used. `--state` takes any snapshot, so a run can also be replayed from
another state, and `--out FILE` writes the result to a file.

`python3 tools/sched.py timeline FILE --root DIR` runs a whole schedule file
on a copy of the layout under DIR, as the production scheduler does.

## 4. Feeds

Every feed file a run read stays under `feeds/` (`feeds.md`).

## 5. Operator corrections

Operators correct the state with `tools/admin.py add <path> <amount>`, which
loads the file, adds the amount, and saves a revision with job `admin`. Each
correction has a ticket and is logged in `logs/ops.log` with the snapshots it
loaded and wrote. Corrections are authorized changes, part of the books, and
not defects of the jobs.

## 6. Audits

The finance team compares the state with the upstream books at fixed times
and leaves the result in `logs/audit/`: each line names a field whose value in
the state (`state=`) differs from the books (`books=`), and the header names
the snapshot that was the state at that time. The books are kept by the trip
system and the member app and follow the rules in `jobs.md` and `fares.md`.
An audit shows where values ended up, not which run made them wrong; a value
made wrong once stays wrong in every later revision until something changes
it again.
