# Operations

## 1. Logs

All times are UTC.

- `logs/queue/<date>.log`: the queue's own record, in order. One `enqueue`
  line per message, with its id, job type, producer and payload:

  ```
  2027-06-08T14:02:11.204Z enqueue m0004821 refund.issue producer=billing {"amount":1250,"card":"ok","idem":"rf-o101377-1","order":"o101377","sent_at":"2027-06-08T14:02:11.010Z","v":3}
  ```

  and one line when the message ends (`queue.md` 1): `done <id>`,
  `duplicate <id> of=<holder id>`, or `dead-letter <id> reason=<reason>`.
- `logs/worker.log`: every delivery that got as far as a result, a refusal,
  a lost lease or an abandonment: `<id> receive=<n>` followed by
  `ok ms=<ms>`, `error ms=<ms> "<detail>"`,
  `throttled ms=<ms> retry_after=<ms>ms "<detail>"`,
  `rejected ms=<ms> "<detail>"` (a result line, written when the handler
  returns, with `ack refused (lease lost)` when it came too late),
  `refused "<why>"` (the payload or key check), `lease expired` or
  `abandoned`.
- `logs/service.log`: `started config=r<rev>` (with the checkpoint it read),
  `stopping checkpoint=<file>`, `config reload rev=<rev>`, and once an hour a
  `stats` line for the hour before it: messages enqueued, ended `done`,
  `duplicate` and `dead_lettered` in the hour, the messages pending at the
  end of the hour (`backlog`) and the dead-letter queue's size (`dlq`).
- `logs/downstream.log`: every change of state of a downstream service, as
  the services report it: `ok`, `down`, or `throttled` with the
  `retry_after` it sends back.
- `logs/deploy.log`: releases, with the time each went live, and other
  teams' releases that change what producers send.
- `logs/config.log`: configuration revisions, with the time each was applied.
- `logs/ops.log`: notes by the operators.

## 2. Restarts and deploys

The queue stops before a deploy or a host change and starts again a few
seconds later. Producers hold their messages while it is stopped. A release
runs from the first `started` line after its deploy time until the next
deploy; the `drain` lines in the deploy log mark the deploy window, and the
queue keeps delivering until `stopping`. A host restart without a deploy (for
example a kernel patch) starts the release that was already running.

## 3. Checkpoints

At `stopping` the queue writes its state to `var/checkpoints/<time>.json`
and the next `started` line reads it: every pending message (payload,
receives, failures, lost leases, when it is ready, whether it holds its key)
and every held idempotency key. Nothing else carries over a restart.

## 4. Applying a configuration

`config reload` applies a revision without a restart (`config.md`).

## 5. Replaying traffic

```
python3 tools/replay.py [--since TIME] [--until TIME] [--diff] [--times] [--pkg DIR] [--root DIR]
```

reads the logs, the configuration history and the checkpoints, and runs
every message, reload, stop and start through the package in log order,
starting at the last `started` line at or before `--since` (the first one
without it) with the checkpoint that line read. Each handler call gets the
answer its downstream service gave at that moment according to
`downstream.log`, and takes as long as the same call took in the logs.

It prints one line per message that ended at or after `--since` (or is still
pending) with how the log and the replay ended it, for example

```
m0004821 logged=dead-letter:key-conflict@2027-06-08T18:02:14.411Z replay=done
```

and a summary line. `--diff` prints only the messages where the two differ;
`--times` adds when the replay ended each message and after how many
receives. Times are written as in the logs, for example
`2027-06-08T14:00:05.000Z`. `--pkg` names a directory that holds a
`quayside` package to use instead of `/app/quayside`, for example a copy
with one change, and `--root` a directory laid out like `/app` with other
logs. Every `started` line runs the same package, so a replay reproduces the
log only over the time the release in `--pkg` actually ran.
