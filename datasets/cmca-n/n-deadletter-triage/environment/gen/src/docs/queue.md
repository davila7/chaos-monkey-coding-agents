# Queue

All times are in milliseconds. A job type's settings (`max_attempts`,
`backoff`, `backoff_max`, `visibility`) are its own values from
`[jobs."<type>"]` in the configuration, or the global ones where it sets
none (`config.md` 3).

## 1. Messages and how they end

A producer enqueues a message with an id, a job type and a JSON payload
(`payloads.md`). The message is ready at once. Every message ends exactly
once:

- `done`: a delivery's handler returned `ok`.
- `duplicate`: the message repeats one that holds its idempotency key
  (section 5). Its handler does not run.
- `dead-letter`: the message is moved to the dead-letter queue with one of
  the reasons in section 6.

## 2. Deliveries

Workers deliver every ready message at once; there is no limit on how many
deliveries run at the same time. A delivery:

1. counts one more receive of the message;
2. checks the payload (`payloads.md`); a payload that fails the check goes to
   the dead-letter queue with reason `schema-rejected`, on any receive;
3. on the message's first delivery that passes the payload check, checks its
   idempotency key (section 5);
4. takes a lease (section 4) and runs the handler.

When several things are due at the same millisecond, results come first,
then lease expiries, then deliveries.

## 3. Results

The handler returns one of four results:

- `ok`: the message is `done`.
- `rejected`: the downstream service refused the message for good (for
  example an expired card). The message goes to the dead-letter queue with
  reason `rejected`; it is not retried.
- `throttled`: the downstream service asked for fewer calls and said when to
  come back (`retry_after`). The message is ready again `retry_after` after
  the result. A throttled delivery is not a failure: it does not count
  toward `max_attempts`, however many times it happens.
- `error`: the downstream service failed (a timeout, a 5xx). This is a
  failure. When the message has failed `max_attempts` times it goes to the
  dead-letter queue with reason `attempts-exhausted`. Otherwise it is ready
  again after the backoff for its failure count `n`:
  `backoff * 2^(n-1)`, never more than `backoff_max`. With `backoff = "1m"`
  and `backoff_max = "15m"` the waits are 1, 2, 4, 8, 15, 15, ... minutes.

## 4. Leases

A delivery holds the message for `visibility`, its job type's visibility
timeout, from the time it starts. While the handler runs, and
`lease.heartbeat` is true, the worker renews the lease every third of the
job type's visibility timeout (integer division of the milliseconds): each
renewal moves the end of the lease to `visibility` after the renewal. A
renewal is only possible while the lease still holds, so with heartbeats on
a lease does not run out while its worker is up. With `heartbeat = false`
nothing renews it.

If the lease runs out before the handler returns, the message is ready again
at that moment and is delivered again; the result of the old delivery, when
it comes, is refused and changes nothing. A lease that runs out at the same
millisecond as the handler returns does not run out: the result counts. Each
lease that runs out counts as a lost lease; when a message has lost
`lease.max_lost` leases it goes to the dead-letter queue with reason
`lease-lost`.

When the queue stops (`operations.md` 2), running deliveries are abandoned
without a result. Their message is ready again when its lease, as it stood at
the stop, ends; an abandoned delivery is not a lost lease.

## 5. Idempotency keys

A producer that is not sure a message went through sends it again with the
same payload. The key of a message is:

- `<type>:<idem>` when the payload is schema 3 or later and has a non-empty
  `idem` field;
- `<type>:<idem_key>` when the payload is schema 2 and has a non-empty
  `idem_key` field;
- `<type>:order:<order>` otherwise.

A schema 3 payload's `idem_key` and a schema 2 payload's `idem` play no part
in the key.

The first message to pass the key check with a free key holds it. Another
message with the same key is a `duplicate` when its payload equals the
holder's, every field but `sent_at` compared, and goes to the dead-letter
queue with reason `key-conflict` when it differs. A message never conflicts
with itself: later deliveries of the holder skip the check. The holder keeps
the key while it is pending and for `dedupe.window` after it is `done`; a
holder that goes to the dead-letter queue frees the key at once, so a fixed
message can be sent again.

## 6. Dead-letter reasons

| Reason | When |
|---|---|
| `schema-rejected` | the payload check failed (section 2) |
| `key-conflict` | the key is held by a message with another payload (section 5) |
| `rejected` | the handler returned `rejected` (section 3) |
| `attempts-exhausted` | the message failed `max_attempts` times (section 3) |
| `lease-lost` | the message lost `lease.max_lost` leases (section 4) |
