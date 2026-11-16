# Configuration

The live file is `config/queue.toml`. Every revision ever applied is kept in
`config/history/r<rev>.toml` (three digits), and `logs/config.log` says when
each was applied. A reload takes effect for deliveries that start after it;
running deliveries keep the lease they started with.

## 1. Example

```toml
rev = 7
accept_schema = [2, 3]

[retry]
max_attempts = 6
backoff = "1m"
backoff_max = "15m"

[lease]
visibility = "10m"
heartbeat = true
max_lost = 4

[dedupe]
window = "24h"

[jobs."refund.issue"]
max_attempts = 10
backoff = "2m"
```

## 2. Keys

| Key | Meaning |
|---|---|
| `rev` | the revision number |
| `accept_schema` | the payload schema versions the queue accepts (`payloads.md` 1) |
| `retry.max_attempts` | failures before `attempts-exhausted` (`queue.md` 3) |
| `retry.backoff`, `retry.backoff_max` | the first wait after a failure and the longest (`queue.md` 3) |
| `lease.visibility` | the visibility timeout (`queue.md` 4); at least 3 seconds |
| `lease.heartbeat` | whether running deliveries renew their lease (`queue.md` 4) |
| `lease.max_lost` | lost leases before `lease-lost` (`queue.md` 4) |
| `dedupe.window` | how long a `done` message keeps its key (`queue.md` 5) |

A duration is a whole number of seconds (`90`), or a string with one unit:
`ms`, `s`, `m` or `h` (`"90s"`, `"2m"`).

## 3. Job types

A `[jobs."<type>"]` table may set `max_attempts`, `backoff`, `backoff_max`
and `visibility` for one job type. Everything it does not set comes from the
global tables. `heartbeat`, `max_lost`, `accept_schema` and the dedupe window
are global only.

Long handlers such as invoice renders do not need a long visibility timeout:
with heartbeats on, the lease is renewed for as long as the handler runs, and
a short timeout brings back the messages of a worker that died sooner.
