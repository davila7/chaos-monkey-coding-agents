# Triage

How a dead-lettered message is traced to its cause.

## 1. Where to start

The `stats` lines in `logs/service.log` show, hour by hour, how many
messages went to the dead-letter queue. `logs/queue` has the reason the queue
gave for each one, and `logs/worker.log` every delivery before it. The
reason says what the queue decided, not why: a message can run out of
attempts because of an outage or because of a wrong count. A replay
(`operations.md` 5) runs the logged traffic through any copy of the package,
so the effect of one change to the code on every message can be measured:
run the copy and compare with the log.

## 2. Things that look wrong and are not

- A message whose handler failed `max_attempts` times while its downstream
  service was down for longer than the backoff covers.
- A refund to an expired card (`rejected`).
- A payload that really lacks a required field or has a schema version the
  configuration does not accept.
- A resend whose payload differs from the message holding its key, for
  example a support edit of an amount that was already refunded.
- A resend with the same payload (`duplicate`).
- Messages ended by an earlier release did what that release did. Check
  `logs/deploy.log`.
- A configuration revision that only moves or comments things.

## 3. Cause classes

| Class | Meaning |
|---|---|
| `retry-budget` | A message is given fewer (or more) failures than the docs allow before `attempts-exhausted` |
| `backoff` | The wait between deliveries after a failure is not the one the docs give |
| `idempotency` | Two messages get the same key when the docs give them different ones, or the reverse |
| `visibility` | A lease ends earlier or later than the docs give |
| `schema` | The payload check refuses a payload the docs accept, or the reverse |
| `routing` | A message reaches the wrong handler or downstream service |
| `ordering` | Things due at the same time happen in another order than the docs give |
| `clock` | Times are read, ordered or compared wrongly |
