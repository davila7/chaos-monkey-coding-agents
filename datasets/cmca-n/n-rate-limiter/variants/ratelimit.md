# Rate limiting (release 2.7)

Status: approved. The stage does not exist yet in 2.6.

The edge limits how fast each client, tenant or route may send requests. The
limits are part of the node configuration. The same code runs in production
and in `replay`, and replays of captured traffic are compared exactly with
what this note specifies, response headers and summary included, so every
rule below is part of the contract.

## 1. Where the stage runs

The stage is named `ratelimit`. It runs after `auth` and before `upstream`
(`pipeline.md`, section 1). Requests answered by `route` or `auth` never reach
it: they are not counted, charged or given rate limit headers.

A configuration without `[[limit]]` sections replays exactly as in release
2.6: no request is limited, no header is added and `summary.json` keeps its
2.6 keys.

## 2. Example

    [clients]
    trusted_proxies = ["192.168.0.0/16", "2001:db8:ffff::/48"]

    [[limit]]
    name = "by-address"
    key = ["client"]
    rate = 5
    per = "1s"
    burst = 10

    [[limit]]
    name = "writes"
    algorithm = "fixed-window"
    key = ["tenant", "route"]
    routes = ["baskets"]
    methods = ["POST", "put"]
    rate = 100
    per = "1m"
    cost = { POST = 2 }

## 3. [clients]

| Key | Type | Meaning |
|---|---|---|
| `trusted_proxies` | list of strings | networks in CIDR form (`10.0.0.0/8`, `2001:db8::/32`) whose machines are trusted to add `X-Forwarded-For` entries. No network is trusted when left out |

A network with bits set after its prefix length (`10.0.0.1/8`) is an error.
A single address may be written without a prefix length and means that one
address.

## 4. [[limit]]

4.1 One table per limit, in the order they are checked:

| Key | Type | Meaning |
|---|---|---|
| `name` | string | required; unique among the limits |
| `algorithm` | string | `token-bucket` (when left out) or `fixed-window` |
| `rate` | int | required, at least 1: tokens added per `per` (token bucket) or requests allowed per window (fixed window) |
| `per` | string | required: a whole number followed directly by `ms`, `s`, `m` or `h` (`"250ms"`, `"1s"`, `"10m"`). No fraction, no space, no other unit |
| `burst` | int | token bucket only, at least 1: the bucket's capacity; equal to `rate` when left out. Giving `burst` for a fixed window is an error |
| `key` | list of strings | required, not empty: the key parts (section 6); a part may not appear twice |
| `routes` | list of strings | route names the limit covers; every route when left out. A name that is not a route of the file is an error |
| `methods` | list of strings | methods the limit covers, in any case; every method when left out |
| `cost` | table | method (any case) to cost, a positive integer; a method not listed costs 1. Two entries for the same method are an error |
| `exempt` | list of strings | client networks in CIDR form (section 3 rules) that the limit does not cover |

4.2 The capacity of a limit is `burst` for a token bucket and `rate` for a
fixed window.

## 5. Which limits cover a request

A limit covers a request when all of these hold:

1. the request's route is in `routes` (or `routes` is left out);
2. the request's method is in `methods` (or `methods` is left out);
3. every key part of the limit has a value for the request (section 6);
4. the client address (section 7) is in none of the `exempt` networks.

A request no limit covers passes the stage unchanged.

## 6. Key parts

Each limit keeps separate state for each distinct combination of its key part
values. Two limits never share state, even with equal keys.

| Part | Value |
|---|---|
| `tenant` | the tenant name; no value when the request has no tenant |
| `client` | the client address (section 7): an IPv4 address in dotted form, or for IPv6 the `/64` network that holds the address, in compressed form (`2001:db8:42:7::/64`) |
| `route` | the route name |
| `method` | the method in upper case |
| `header:NAME` | the first header named NAME (in any case), with spaces and tabs at both ends removed; no value when there is no such header or when the value is empty after that |

## 7. The client address

7.1 When the request's peer is not in a trusted network, the client address
is the peer.

7.2 Otherwise the address comes from `X-Forwarded-For`. Take every
`X-Forwarded-For` header of the request in order, split each value on commas
and remove spaces and tabs around each entry; this is the list of entries,
oldest hop first. Walk it from the last entry to the first:

* an entry that is an address in a trusted network is skipped;
* the first entry that is an address outside every trusted network is the
  client address;
* an entry that is not an address ends the walk: the client address is the
  address of the entry examined just before it (the one to its right), or the
  peer when it is the last entry.

When every entry is a trusted address, the client address is the first
entry. When there are no entries, it is the peer.

7.3 Address forms. An entry may carry a port: `198.51.100.4:8080`, or for
IPv6 `[2001:db8::7]:443`; the port is not part of the address. An IPv6
address in brackets without a port is also allowed. An IPv4 address mapped
into IPv6 (`::ffff:198.51.100.4`) is the IPv4 address, for the trusted and
exempt checks and for the key. Anything else is not an address.

## 8. Time

The stage keeps its own clock. For each request that reaches the stage,
`now` is the request's `ts` in milliseconds, or the `now` of the previous
request that reached the stage when that is later: the stage's clock never
goes back. The clock and all limit state last for the whole replay, across
trace files.

## 9. Algorithms

9.1 Arithmetic. Token levels are exact rational numbers. Binary floating
point is not exact enough for this and must not be used for levels, waits or
the header values derived from them.

9.2 Token bucket. A bucket holds between 0 and `burst` tokens. A key's bucket
is created full the first time a request with that key is checked. Before a
request is checked, the bucket is refilled for the time since it was last
refilled: `level = min(burst, level + elapsed_ms * rate / per_ms)`. The limit
allows a request of cost `c` when `level >= c`; charging takes `c` tokens
away.

9.3 Fixed window. Time is cut into windows of `per` milliseconds counted
from the Unix epoch: the window of `now` starts at
`now - now mod per_ms`. Each key counts the cost charged in the current
window, starting from 0 in every new window. The limit allows a request of
cost `c` when `used + c <= rate`; charging adds `c`.

9.4 A limit always refuses a request whose cost is greater than its capacity.

## 10. The decision

10.1 The request is allowed when every limit that covers it allows it. Then
every covering limit is charged.

10.2 Otherwise the stage answers 429, and no limit is charged at all, not even
the ones that allowed the request. The limits that refused it are the
refusing limits.

## 11. Response headers

11.1 When at least one limit covers the request, the response carries
`RateLimit-Limit`, `RateLimit-Remaining` and `RateLimit-Reset`, describing one
limit, the deciding limit. A 429 response also carries `Retry-After`, except
as given in 11.4. Values are whole numbers written in decimal. Header names are
spelled as here.

11.2 The deciding limit:

* for an allowed request, the covering limit with the smallest remaining
  value after charging (11.3); between equal values, the one listed first;
* for a refused request, the refusing limit with the longest wait (11.3).
  A limit that refuses under 9.4 counts as having a longer wait than any
  other; between equal waits, the one listed first.

11.3 Values of a limit, at `now`, after charging when the request is allowed
and with nothing charged when it is refused:

| | Token bucket | Fixed window |
|---|---|---|
| limit | `burst` | `rate` |
| remaining | the level, rounded down to a whole number | `rate - used` |
| reset | the seconds until the bucket is full again: `(burst - level) * per_ms / rate` milliseconds, in seconds rounded up | the seconds until the window ends, rounded up |
| wait | the milliseconds until `level` reaches the request's cost: `(c - level) * per_ms / rate` | the milliseconds until the window ends |

11.4 `Retry-After` is the deciding limit's wait in seconds, rounded up, and at
least 1. When the deciding limit refuses under 9.4, there is no
`Retry-After` header.

## 12. Summary

When the configuration has `[[limit]]` sections, `summary.json` gets the key
`rl_refused`: an object with one entry per limit (all of them, including those
that never refused anything) giving the number of 429 decisions in which that
limit was a refusing limit.

## 13. Configuration errors

Every rule of sections 3 and 4 that a file breaks is a `ConfigError` (exit
status 2), found when the configuration is loaded, before any trace is read.
This includes unknown keys in `[clients]` and `[[limit]]`, wrong types, a
`burst` or `rate` below 1, an unknown algorithm or key part, an empty
`header:` name, and a `per` of zero.
