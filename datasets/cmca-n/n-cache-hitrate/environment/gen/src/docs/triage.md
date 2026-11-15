# Triage

How a lost hit is traced to its cause.

## 1. Where to start

The `stats` lines in `logs/service.log` show the hit rate and the time to
answer hour by hour. The access log shows every request with what the cache
did, so two requests that should share an entry and both missed can be found.
A replay (`operations.md` 4) runs the logged traffic through any copy of the
package, so the effect of one change to the code on every request can be
measured: run the copy and compare with the log.

## 2. Things that look wrong and are not

- Misses after a restart or a flush, until the entries are stored again.
- The first request of a key, and the first request after its entry expired.
- The purged book or author itself after a purge.
- A slow upstream: misses take longer, but the hit rate does not change.
- Requests served by an earlier release did what that release did. Check
  `logs/deploy.log`.
- A configuration revision that only moves or comments things.

## 3. Cause classes

| Class | Meaning |
|---|---|
| `key-params` | A query parameter takes part in the key when the docs leave it out, or the reverse |
| `key-normalize` | A parameter value goes into the key without the normalization the docs give, or with another |
| `key-vary` | The header-derived part of the key takes more (or fewer) values than the docs allow |
| `ttl` | An entry expires earlier or later than its route's configured ttl |
| `invalidation` | A purge removes entries it must leave, or leaves entries it must remove |
| `capacity` | Entries are dropped before they expire to make room |
| `routing` | A request is matched to the wrong route, or a cached route is passed through |
| `clock` | Request times are read, ordered or compared wrongly |
