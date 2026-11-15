# Changelog

## 2.4.0

- Search terms are normalized before they go into the key (`cache.md` 2.1).
  2.3.1 kept `q` as sent, so `Dune` and `dune` were stored twice.
- Durations are kept in milliseconds, and a `ttl` can be written with the
  `ms` unit (`config.md` 3).
- Locale negotiation rewritten as one function used by the key builder and
  by the response headers (`locale.md`).
- The tracking parameter rule moved into the key builder next to
  `ignore_params` (`cache.md` 2.1).
- Purge removes entries by key prefix instead of walking a per-id index,
  which used memory for every stored key.

## 2.3.1

- `ignore_params` read from the configuration instead of a list in the code.
- Authors pages vary on nothing; they have no localized text.

## 2.3.0

- `PURGE` for authors.
- Configuration reloads without a restart.

## 2.2.4

- Hourly `stats` lines in the service log.
