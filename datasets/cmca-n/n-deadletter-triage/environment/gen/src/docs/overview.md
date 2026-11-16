# Overview

`quayside` is the job queue of the shop back office. Producers enqueue
messages; workers deliver each message to the handler of its job type, and
the handler calls one downstream service:

| Job type | Producer | Downstream service | What the handler does |
|---|---|---|---|
| `email.send` | `notifier`, `campaigns` | `mailer` | sends one email |
| `refund.issue` | `billing`, `support`, `pos` | `payments` | issues one refund to a card |
| `invoice.render` | `storefront` | `pdfgen` | renders the invoice PDF of an order, one page section per line |
| `stock.sync` | `storefront` | `inventory` | moves stock for an order |

A message ends in one of three ways (`queue.md` 1): its handler succeeds
(`done`), it repeats a message that already holds its idempotency key
(`duplicate`), or it goes to the dead-letter queue (`dead-letter`, with a
reason). Messages in the dead-letter queue stay there until an operator
looks at them; nothing in the queue retries them.

## Layout

- `quayside/`: the package. `broker.py` runs deliveries, leases and results;
  `retry.py` decides what a result does to a message; `lease.py` computes
  leases and heartbeats; `dedupe.py` builds and holds idempotency keys;
  `schema.py` checks payloads; `config.py` reads the configuration;
  `checkpoint.py` writes and reads the state kept across restarts.
- `config/queue.toml`: the live configuration. `config/history/` keeps every
  revision (`config.md`).
- `logs/`, `var/checkpoints/`: what the queue did (`operations.md`).
- `tools/replay.py`: replays the logged traffic through a copy of the
  package (`operations.md` 5).
- `tests/`: unit tests, run with `python3 -m unittest` from this directory.
