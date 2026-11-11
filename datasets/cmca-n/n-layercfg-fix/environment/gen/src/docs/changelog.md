# Changelog

## 3.1.0

- `get` prints the value of one key (`overview.md` 4.3).
- A `%include` line may end with a comment (`include.md` 1.1).
- A reference names the section before its last dot, so references reach
  dotted sections such as `server.tls` (`interp.md` 3.1).

## 3.0.0

- References are expanded once the whole config has been merged, and see the
  final value of each key (`interp.md` section 4). Up to 2.x each value was
  expanded when its line was read, against what had been read so far, so
  `path = ${path}:/opt/bin` extended an earlier value. That is now a cycle.
- `KB`, `MB`, `GB` and `TB` are powers of 1000; the binary units are `KiB`,
  `MiB`, `GiB` and `TiB` (`types.md` section 8). Up to 2.x every size unit
  was a power of 1024; the size policy behind that rule is withdrawn (see
  `archive/2025-size-units.md`).
- `\$` in double-quoted values (`syntax.md` 5.2).

## 2.4.0

- Template sections (`syntax.md` 3.6, `output.md` 2.3).
- List items are trimmed and empty items are dropped (`types.md` 9.1).
- The summary listing `OUT/summary.json`.

## 2.0.0

- Shared files and `%include` (`include.md`). After a shared file, the
  including file goes on in its own section (`include.md` 2.2).
- Section names are not case-sensitive (`syntax.md` 3.2).
