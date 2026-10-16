# Configuration files

A configuration is a TOML file. `configs/` holds one per edge node. Every
top-level table or array of tables is a section; the sections a file may hold
are listed here and in the notes they refer to. Any other section is an error,
and so is any key inside a section that its description does not list.

## 1. [server]

| Key | Type | Meaning |
|---|---|---|
| `name` | string | the node name, shown by `check`; `edge` when left out |

## 2. [upstream]

| Key | Type | Meaning |
|---|---|---|
| `timeout` | duration string | upstream timeout, such as `"2.5s"` or `"800ms"`; units `ms`, `s`, `m`, `h`, `d`; 2 s when left out |

## 3. [[route]]

3.1 One table per route:

| Key | Type | Meaning |
|---|---|---|
| `name` | string | unique route name |
| `prefix` | string | path prefix, starting with `/` |
| `methods` | list of strings | the methods the route takes; `["GET"]` when left out. Written in any case; compared in upper case |
| `public` | bool | requests need no API key (section 4); false when left out |
| `status` | int | the 2xx status the upstream answers with in a replay; 200 when left out |

3.2 Matching. A route matches a request when its prefix segments are the first
segments of the request path, ignoring the query string and empty segments:
`/api/v1` matches `/api/v1`, `/api/v1/` and `/api/v1/orders?x=1`, but not
`/api/v10`. When several routes match, the one with the most prefix segments
wins; between equal counts, the one listed first.

At least one route is required.

## 4. [tenants]

    [tenants.northwind]
    keys = ["k-nw-1", "k-nw-2"]

One subtable per tenant, with the API keys of that tenant. A key belongs to
one tenant only.

## 5. Sections of the rate limiting stage

`[clients]` and `[[limit]]` are described in `ratelimit.md`, sections 3 and 4.
