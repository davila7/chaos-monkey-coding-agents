# Outputs

Every command writes to standard output; errors go to standard error
(`conventions.md`, section 2). Versions are printed as written in the index
file, build metadata included.

## 1. Exit statuses

| Status | Meaning |
|---|---|
| 0 | done, no problem |
| 2 | usage error |
| 3 | an index or manifest file breaks its format |
| 4 | done, with problems (resolve, check, outdated), or nothing matched (match) |

## 2. resolve

`--format json` (the default) prints the lock document:

```json
{
  "root": "project-014@1.2.0",
  "packages": [
    {"name": "arcor", "version": "2.3.1", "by": "project-014@1.2.0"},
    {"name": "fenlum-io", "version": "1.4.0+b7", "by": "project-014@1.2.0"}
  ],
  "problems": [
    {"package": "zetnex", "range": "~0.3.1", "by": "fenlum-io@1.4.0+b7", "code": "conflict", "chosen": "0.4.0"}
  ]
}
```

(shown compact; the real output is indented by two spaces per level).

- `packages` holds every chosen release, sorted by package name, with the
  label of the requirement that chose it.
- `problems` holds the problems in the order they happened
  (`resolve.md`, section 5). `range` is the range text exactly as written.
  `chosen` is present only for `conflict`.

`--format text` prints the root label, then one line per chosen package
(name padded to the longest name, two spaces, version, two spaces,
`(from <by>)`), then, if there are problems, `problems:` and one line per
problem: `  <package> <range as a JSON string> from <by>: <code>`, followed by
` (chosen <version>)` for a conflict.

## 3. show

The package name, then one line per release, lowest precedence first:
two spaces, the version, a tab, the flags (`prerelease`, `yanked`, joined by
a comma, or `-`), a tab, the dependencies as `name range` joined by `, ` (or
`-`).

## 4. match

The candidates for the range (`resolve.md`, section 4), highest first, one
version per line. Exit status 4 when there is none. A range that cannot be
read prints `pinset: <code>: <message>` on standard error and exits with
status 4.

## 5. check

Reads the whole index (a format error exits with status 3, as for every
command). Then, for every package in name order, every release lowest first
and every dependency in file order, prints one line for a dependency on a
package that is not in the index or with a range that cannot be read:

    <package>@<version>: <dependency> <range as a JSON string>: <code>

The last line is `<P> packages, <R> releases, <N> problems`. Exit status 4
when N is not zero.

## 6. why

Resolves the manifest and prints the chain of labels from the manifest to the
package, joined by ` -> `. A package that is not in the resolution is a usage
error.

## 7. outdated

Resolves the manifest, then prints one line per direct requirement, in
manifest order (`[dev-dependencies]` too with `--dev`). Columns, separated by
two spaces and padded to the widest entry of the column, the last one
without padding and trailing spaces removed:

1. the package name;
2. the range text as written;
3. the version the resolution chose for that package, or `-`;
4. the newest release of the package that is neither yanked nor a
   prerelease, or `-`;
5. a mark: empty when the range accepts that newest release, `outside` when it
   does not, the range's error code when the range cannot be read,
   `unknown-package` for a package that is not in the index.

Exit status 4 when any line carries a mark.
