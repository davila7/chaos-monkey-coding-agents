# The cache

## 1. Cached requests

| Request | Route | Id |
|---|---|---|
| `GET /books/<id>` | `books` | the book id, digits without a leading zero |
| `GET /authors/<id>` | `authors` | the author id, same form |
| `GET /search` | `search` | none |

Any other request (`/health`, other paths, other methods) is passed through
and not cached; the access log shows `cache=-` for it. `PURGE` requests
(section 4) are answered by the cache itself and also log `cache=-`.

## 2. Keys

Two requests share an entry exactly when their keys are equal. The key is

    <route>|<id>|<parameters>|<locale>

2.1 `<parameters>` is built from the query string:

- Every query parameter takes part, except parameters whose name is listed in
  `ignore_params` (`config.md` 2) and parameters whose name starts with
  `utm_`. Names are compared exactly, case included: `UTM_Source` and
  `refine` take part.
- Values are taken as decoded from the query string (`+` is a space). The
  value of `q` is normalized: lowercased, spaces at both ends removed and
  every run of whitespace inside replaced by one space, so `Dune  Messiah `
  and `dune messiah` are the same search. Other values are kept as they are.
- The kept `name=value` pairs are sorted (by name, then value) and joined
  with `&`, so the order in which a client sends parameters does not matter.
- A request without parameters, or whose parameters are all left out, has an
  empty `<parameters>`.

2.2 `<locale>` is the locale negotiated from the request's `Accept-Language`
header (`locale.md`), spelled exactly as in `locales`, when the route's
`vary` list names `Accept-Language`; otherwise it is empty. A route that
varies on the locale therefore has at most one entry per supported locale for
a given id and parameters.

## 3. Expiry

A miss stores an entry that expires `ttl` after the time of the request, with
the `ttl` of the request's route in the configuration in force at that time
(`config.md` 3). A request strictly before the expiry time is a hit; a request
at or after it is a miss and stores a new entry. A configuration reload does
not change the expiry of entries already stored.

## 4. Purge

The catalog sends `PURGE /books/<id>` when a book changes and
`PURGE /authors/<id>` when an author changes. A purge removes every entry of
that one book or author, whatever its parameters and locale, and no other
entry: purging book `12` leaves books `120` and `1203` alone. Search entries
are never purged; they age out with their `ttl`.

## 5. Restart and flush

The store is in memory. A restart starts with an empty store, and an operator
flush (`operations.md` 3) empties it. The requests after either are misses
until the entries are stored again.

## 6. Size

The store has no entry limit and never evicts an entry before it expires.
Expired entries are dropped when a request finds them.
