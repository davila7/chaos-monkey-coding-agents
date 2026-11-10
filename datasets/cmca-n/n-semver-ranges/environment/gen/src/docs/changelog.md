# Changelog

## 2.0.0 (in progress)

- Range syntax, specified in `ranges.md`: caret, tilde, wildcards, hyphen
  ranges, comparator sets and `||`. Not implemented yet: `pinset/ranges.py`
  still holds the 1.x reader.
- Agreed in review of `ranges.md`:
  - a caret never moves past the first non-zero part, so `^0.2.3` stops
    before `0.3.0` and `^0.0.3` before `0.0.4`; this matches what the other
    package tools the team uses do with 0.x versions;
  - a range that cannot be read is reported with its code, never repaired;
  - prereleases stay opt-in: only an alternative that names a prerelease of
    the same release lets prereleases of that release through.
- `tests/test_ranges.py` added with the first cases from `ranges.md`. They
  fail until ranges land.
- `data/` refreshed from the team index: most manifests and many index files
  now use 2.0 ranges.

## 1.4.0

- `why` and `outdated` commands.
- `resolve --format text`.

## 1.3.0

- Index files may list prereleases and versions with build metadata
  (`versions.md`). Only an exact range chooses a prerelease.
- `show` prints a `prerelease` flag.

## 1.2.0

- Yanked releases: an entry may carry `"yanked": true`; only an exact range
  chooses it.
- `[dev-dependencies]` and `resolve --dev`.

## 1.1.0

- `check` command.
- Problems no longer stop the resolution; they are listed in the lock
  document.

## 1.0.0

- First release: `resolve`, `show` and `match`; ranges are one version or a
  lower bound with `>=`.
