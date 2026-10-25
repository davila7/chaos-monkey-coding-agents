# Code conventions

## 1. General

- Standard library only. Python 3.12.
- Modules are small and named after what they do.
- Text files are read and written as UTF-8. JSON output uses two-space
  indentation, keeps non-ASCII characters as they are and ends with a newline.
- Nothing depends on the clock, the environment or the order in which the
  file system lists files: index files are read in name order.

## 2. Errors and exit statuses

| Class | Exit status | Used for |
|---|---|---|
| `UsageError` | 2 | a wrong command line, an unknown package on the command line |
| `DataError` | 3 | an index or manifest file that is missing, unreadable or breaks `index.md` or `manifest.md` |
| `VersionError` | not an exit | a text that is not a version; callers turn it into one of the above |
| `RangeError` | not an exit | a range that cannot be read; carries `code` (`ranges.md`, section 7) |

`pinset.cli.main` prints `pinset: error: <message>` on standard error for
`UsageError` and `DataError` and returns the status. A command that found
problems in what it was asked to do (a requirement that cannot be met, a
range that cannot be read) exits with status 4 and still prints its normal
output. Status 0 means no problem.

Error messages are for people. Tests and tools compare exit statuses, codes
and outputs, never message texts.

## 3. Commands

A command is a module under `pinset/commands/` with `HELP`,
`add_arguments(parser)` and `run(args, out) -> int`, listed in `COMMANDS` in
`pinset/commands/__init__.py`. `run` writes its output to `out` and returns
the exit status. `args.index` is always set.

## 4. Public interface

Other tools import these names. Their signatures and behaviour stay as
documented here across 2.0:

- `pinset.version.Version`: `Version.parse(text)`, comparison operators,
  `hash`, `str`, the attributes `major`, `minor`, `patch`, `prerelease`
  (a tuple of identifier strings), `build` (same), `release` and
  `is_prerelease()`.
- `pinset.ranges.parse_range(text) -> Range`; raises `RangeError`.
- `Range.test(version) -> bool`: whether a `Version` satisfies the range
  (`ranges.md`, sections 1 and 8).
- `Range.is_exact() -> bool` (`ranges.md`, section 10).
- `pinset.index.load_index(directory) -> Index`; `Index.get(name)` returns a
  `Package` whose `releases` are sorted by precedence, lowest first.
- `pinset.manifest.load_manifest(path) -> Manifest`.
- `pinset.resolver.resolve(index, manifest, dev=False) -> Resolution`,
  `candidates(package, range)`, `best(package, range)`.
- `pinset.cli.main(argv, out=None) -> int`.

`Range` may hold whatever it needs internally; nothing outside
`pinset/ranges.py` looks inside it.

## 5. Tests

Unit tests live under `tests/`, one module per area, and run from the
directory that holds `pinset/`:

    python -m unittest discover -s tests -t .

`tests/support.py` builds small indexes and manifests in temporary
directories. The tests do not read `data/`.
