# Resolution

`pinset.resolver.resolve(index, manifest, dev=False)` picks at most one
release per package. It is a single pass with no backtracking: a release,
once chosen, stays chosen.

## 1. Requirements

A requirement is a package name, a range text and the label of what asked
for it (`by`). The manifest's label is `<name>@<version>` from `[package]`;
a release's label is `<package>@<version text from the index>`.

## 2. Order

Requirements wait in a first-in, first-out queue. The queue starts with the
manifest's requirements in file order (`manifest.md`, section 2). When a
release is chosen, its dependencies join the end of the queue in the order of
its index entry, with the release's label as `by`.

## 3. One step

For the requirement at the head of the queue:

1. If the package is not in the index: problem `unknown-package`.
2. If the range cannot be read: problem `bad-range` or `bad-version`
   (`ranges.md`, section 7).
3. If a release of the package is already chosen: nothing happens when that
   release satisfies the range; otherwise problem `conflict`, which also
   records the chosen version.
4. Otherwise the resolver chooses the release of highest precedence among the
   candidates (section 4). With no candidate: problem `no-match`. A later
   requirement for the same package gets its own attempt.

A problem never stops the resolution; the requirement is dropped and the
next one is taken.

## 4. Candidates

The candidates for a range are the releases of the package that satisfy it
(`ranges.md`), except yanked releases: a yanked release is a candidate only
for an exact range (`ranges.md`, section 10). `pinset.resolver.candidates`
returns them lowest first, `best` returns the highest or None.

## 5. Problems

| Code | When |
|---|---|
| `unknown-package` | the package is not in the index |
| `bad-range` | the range does not have the shape of a range |
| `bad-version` | a version inside the range is not valid |
| `conflict` | the release already chosen does not satisfy the range |
| `no-match` | no candidate |

Problems are kept in the order they happen.

## 6. Chains

`chain(resolution, name)` follows `by` from a chosen package back to the
manifest and returns the labels from the manifest down to the package. `why`
prints it.
