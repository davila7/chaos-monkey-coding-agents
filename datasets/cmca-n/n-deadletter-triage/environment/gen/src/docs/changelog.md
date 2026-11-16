# Changelog

## 4.2.0

- Exponential backoff is back (`queue.md` 3). 4.1.3 waited `backoff` after
  every failure, so a downstream outage of half an hour used up the whole
  budget of a refund.
- The result handling of a delivery moved into one function, `retry.settle`.
- Heartbeat interval computed in `lease.py` next to the lease itself.
- Idempotency keys read the producer's idempotency field instead of always
  using the order (`queue.md` 5).
- Payloads are checked before the handler runs; a payload that cannot be
  handled goes to the dead-letter queue at once (`schema-rejected`) instead
  of reaching the downstream service on every attempt.

## 4.1.3

- `[jobs."<type>"]` tables can set `visibility`.
- Checkpoints keep held idempotency keys.

## 4.1.2

- Hourly `stats` lines in the service log.
