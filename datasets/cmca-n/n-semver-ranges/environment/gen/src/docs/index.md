# The package index

## 1. Files

The index is a directory of JSON files, one per package, named
`<package>.json`. Files with another extension are ignored. Each file holds an
object with exactly two keys:

```json
{
  "name": "fenlum-io",
  "versions": [
    {"version": "1.4.0", "dependencies": {"arcor": "^2.1.0", "zetnex": ">=0.3.0"}},
    {"version": "1.4.1-rc.2"},
    {"version": "1.3.9", "yanked": true}
  ]
}
```

- `name` is the package name and equals the file name without `.json`.
- `versions` is a non-empty list of release entries, in any order.

A release entry is an object with:

| Key | Required | Value |
|---|---|---|
| `version` | yes | a version (`versions.md`) |
| `yanked` | no | `true` or `false` (default); see `resolve.md`, section 4 |
| `dependencies` | no | an object from package name to range text |

Any other key is an error.

## 2. Names

A package name is 1 to 40 characters: lowercase ASCII letters and digits in
groups joined by single hyphens, starting with a letter (`zetnex`,
`fenlum-io`, `ux2-fmt`).

## 3. Checks at load time

`load_index` reads every file and fails with `DataError` (exit status 3) when:

- a file is not valid JSON or does not have the shape above;
- a name is not a package name or does not match its file name;
- a `version` is not a version;
- two entries of one package have the same precedence (`1.4.0+a` and
  `1.4.0+b` are the same version);
- a dependency name is not a package name or its range is not a string.

Dependency ranges are not parsed at load time. A range that cannot be read
only matters when the resolver reaches it (`resolve.md`, section 5), and
`check` lists all of them (`output.md`, section 5). A dependency on a package
that is not in the index is handled the same way.

## 4. Order

`Package.releases` is sorted by precedence, lowest first. Entries of equal
precedence cannot occur (section 3). The order of `dependencies` inside an
entry is the order of the file and is kept.
