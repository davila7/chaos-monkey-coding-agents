# shelfmark

shelfmark is the cache in front of the catalog API. Clients ask it for book
pages, author pages and search results; it answers from its own store when it
holds a fresh entry for the request (a hit) and otherwise asks the catalog
service, stores the answer and returns it (a miss). Misses cost a round trip
to the catalog and its database, so the hit rate sets most of the latency
clients see.

One process serves all traffic, on host `cache-1`. Its store lives in memory:
a restart or a flush empties it.

## Layout

| Path | What it is |
|---|---|
| `shelfmark/routes.py` | which requests are cached (`cache.md` 1) |
| `shelfmark/keys.py` | the cache key of a request (`cache.md` 2) |
| `shelfmark/locale.py` | Accept-Language negotiation (`locale.md`) |
| `shelfmark/cache.py` | the entry store: expiry, purge, flush (`cache.md` 3 to 5) |
| `shelfmark/config.py` | reads a configuration file (`config.md`) |
| `shelfmark/service.py` | one request at a time through the above |
| `config/cache.toml` | the live configuration; `config/history/` keeps every revision |
| `logs/` | access, service, deploy, configuration, operator and upstream logs (`operations.md` 1) |
| `tools/replay.py` | replays logged traffic through a copy of the package (`operations.md` 4) |
| `tests/` | unit tests: `python3 -m unittest` from this directory |

The package only decides hit or miss and what to store. Talking to the catalog
and writing the logs is done by the server around it, which is not part of
this tree.
