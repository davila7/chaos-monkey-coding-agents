# Payloads

A payload is a JSON object. Every payload has a whole-number schema version
`v` and the time the producer sent it, `sent_at`.

## 1. The check before a handler runs

A payload passes when:

- `v` is a whole number listed in `accept_schema` (`config.md` 2), and
- every required field of its job type is present:

| Job type | Required fields |
|---|---|
| `email.send` | `order`, `to`, `template` |
| `refund.issue` | `order`, `amount`, `card` |
| `invoice.render` | `order`, `lines` |
| `stock.sync` | `order`, `sku`, `qty` |

Fields a job type does not list are ignored, in every schema version, so
that producers can add fields before every handler reads them. A payload is
never refused for carrying them.

## 2. Idempotency fields

- Schema 3 names the producer's idempotency value `idem`.
- Schema 2 named it `idem_key`.

Producers moving from schema 2 to 3 sometimes keep sending the old field
next to the new one; only the field of the payload's own version counts
(`queue.md` 5).

## 3. Producers

| Producer | Job types | Schema |
|---|---|---|
| `notifier` | `email.send` | 2 |
| `campaigns` | `email.send` (newsletters, `order` is `-`) | 2 |
| `billing` | `refund.issue` | 3 |
| `support` | `refund.issue` (resends after a manual edit) | 3 |
| `pos` | `refund.issue` (store terminals) | 3 |
| `storefront` | `invoice.render`, `stock.sync` | 3 |
