# Configuration

## 1. Files and revisions

`config/cache.toml` is the configuration in force. Every revision ever applied
is kept as `config/history/r<rev>.toml` (three digits), and
`logs/config.log` says when each was applied and by whom. Applying a revision
makes the running process reload it (`operations.md` 2); a process that
starts reads the latest applied revision, and its `started` line names it.

## 2. Keys

| Key | Meaning |
|---|---|
| `rev` | revision number, a whole number |
| `locales` | the locales the catalog has text for, in order of preference for partial matches (`locale.md` 2) |
| `default_locale` | the locale of a request that matches none; must be one of `locales` |
| `ignore_params` | query parameter names that stay out of the key (`cache.md` 2.1), in any order |
| `[routes.<route>]` | one table for each of `books`, `authors` and `search` |
| `routes.<route>.ttl` | how long an entry of the route stays fresh (section 3) |
| `routes.<route>.vary` | request headers that take part in the key; only `Accept-Language` is supported |

Comments, blank lines and the order of tables and keys mean nothing.

## 3. Durations

A `ttl` is either a whole number of seconds or a string made of a whole
number and a unit, without spaces inside:

| Written | Duration |
|---|---|
| `600` | 600 seconds (ten minutes) |
| `"750ms"` | 750 milliseconds |
| `"90s"` | 90 seconds |
| `"10m"` | 10 minutes |
| `"6h"` | 6 hours |

`600` and `"10m"` are the same ttl. A `ttl` of `0` stores entries that are
already expired, which turns caching off for the route. Negative numbers,
fractions, other units and booleans are refused when the file is read.
