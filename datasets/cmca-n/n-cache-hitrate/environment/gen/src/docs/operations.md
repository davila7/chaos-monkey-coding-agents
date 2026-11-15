# Operations

## 1. Logs

All times are UTC.

- `logs/access/<date>.log`: one line per request, in the order they were
  served:

  ```
  2027-05-03T14:02:11.204Z r0006021 GET /search?q=salt+river&page=1 status=200 cache=miss ms=187 lang="en-GB,en;q=0.8"
  ```

  The request id, method, target (path and query string as sent), status,
  what the cache did (`hit`, `miss` or `-`, `cache.md` 1), the time to
  answer in milliseconds and the `Accept-Language` header (`-` when the
  request had none).
- `logs/service.log`: what the process did besides serving requests:
  `started config=r<rev>`, `stopping`, `config reload rev=<rev>`,
  `cache flush entries=<n>`, and once an hour a `stats` line for the hour
  before it (cached requests, hits, hit rate, the 50th and 95th percentile of
  the time to answer, and the entries held).
- `logs/deploy.log`: releases, with the time each went live.
- `logs/config.log`: configuration revisions, with the time each was applied.
- `logs/ops.log`: notes by the operators.
- `logs/upstream.log`: the catalog database as its own monitoring sees it,
  every five minutes.

## 2. Restarts, deploys and reloads

The process stops before a deploy or a host change and starts again after
it; it serves nothing in between, and it starts with an empty store. A
release runs from the first `started` line after its deploy time until the
next deploy. A host restart without a deploy (for example a kernel patch)
starts the release that was already running. Applying a configuration
revision does not restart the process: it logs `config reload` and goes on
with the entries it holds.

## 3. Flush

An operator can empty the store without a restart; `service.log` logs
`cache flush` with the number of entries removed, and `ops.log` says why.

## 4. Replaying traffic

```
python3 tools/replay.py [--since TIME] [--until TIME] [--diff] [--pkg DIR] [--root DIR]
```

reads the service and access logs and the configuration history and runs
every request, purge, reload, restart and flush through the package, in log
order, starting with an empty store at the last `started` line at or before
`--since` (the first `started` line without it). It prints, for each request
from `--since` to `--until`, the result in the log and the result of the
replay; `--diff` prints only the requests where they differ. Times are
written as in the logs, for example `2027-05-03T14:00:05.000Z`. `--pkg`
names a directory that holds a `shelfmark` package to use instead of
`/app/shelfmark`, for example a copy with one change, and `--root` a
directory laid out like `/app` with other logs. Every `started` line runs the
same package, so a replay reproduces the log only over the requests the
release in `--pkg` actually served.
