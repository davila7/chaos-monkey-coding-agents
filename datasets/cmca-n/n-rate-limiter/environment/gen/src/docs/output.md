# Replay output

`replay --out DIR` writes two files into `DIR` (created when missing; existing
files are replaced).

## 1. Encoding

Both files are UTF-8 text with LF line ends, written by `json.dumps` with
`sort_keys=True` and `ensure_ascii=False`.

## 2. decisions.jsonl

One line per request, in replay order:

| Key | Value |
|---|---|
| `id` | the request id |
| `status` | the status of the decision (an integer) |
| `route` | the route name, or null when no route matched |
| `tenant` | the tenant name, or null |
| `client` | the address the request claims to come from, for the access log: the first entry of the first `X-Forwarded-For` header, or the peer when there is none. It is not checked; it is not the address any stage uses to identify a client |
| `headers` | the response headers the stages added, name to value (both strings) |

## 3. summary.json

Written with `indent=2`. Keys:

| Key | Value |
|---|---|
| `requests` | number of requests replayed |
| `status` | status (as a string) to the number of decisions with that status |
| `routes` | route name to the number of requests matched to it; `(none)` for requests without a route |

A stage may add keys through its `summary(state)` function
(`conventions.md`, section 4); `ratelimit.md` says which key the rate limiting
stage adds.
