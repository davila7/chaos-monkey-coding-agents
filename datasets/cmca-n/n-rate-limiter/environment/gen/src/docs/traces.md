# Trace files

## 1. Files

`traces/` holds captured traffic, one JSON Lines file per capture window,
named after the window's start. Each non-empty line is one request. Blank
lines are skipped.

## 2. A request

    {"id": "q-0001", "ts": "2025-05-06T09:00:00.125Z", "peer": "192.168.4.7",
     "method": "GET", "path": "/api/v1/orders/77?expand=lines",
     "headers": [["X-Api-Key", "k-nw-1"], ["X-Forwarded-For", "192.168.200.9"]]}

| Field | Meaning |
|---|---|
| `id` | request id, unique within a capture |
| `ts` | when the edge logged the request, UTC, millisecond precision |
| `peer` | the address of the TCP peer that sent the request to the edge |
| `method` | HTTP method, in the case the client sent it (the reader converts it to upper case) |
| `path` | path with query string, as sent |
| `headers` | the request headers as `[name, value]` pairs in the order received; a name may appear more than once |

## 3. What to expect in captured traffic

- Lines are in the order the edge logged them. The `ts` of each line comes
  from the edge worker that took the request, and the workers' clocks are not
  perfectly in step, so a line can carry a time slightly earlier than the line
  before it.
- Header names come in any case.
- Most clients reach the edge through the load balancers and the partner
  proxies listed in each configuration; those add `X-Forwarded-For` entries.
  Clients can also send an `X-Forwarded-For` header of their own, with any
  content, and some intermediaries send the header more than once.
- Addresses are IPv4 or IPv6. Some intermediaries write a port after the
  address, and IPv6 addresses then appear in brackets.
