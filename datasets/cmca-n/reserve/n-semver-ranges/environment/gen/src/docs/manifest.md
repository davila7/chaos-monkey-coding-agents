# Project manifests

A manifest is a TOML file that names a project and the packages it needs.

```toml
[package]
name = "project-014"
version = "1.2.0"

[dependencies]
fenlum-io = "^1.4"
arcor = ">=2.1.0 <2.4.0 || 3.0.0-rc.4"

[dev-dependencies]
zetnex = "~0.3.1"
```

## 1. Tables

| Table | Required | Content |
|---|---|---|
| `[package]` | yes | exactly `name` (a package name, `index.md` section 2) and `version` (a version) |
| `[dependencies]` | no | package name to range text |
| `[dev-dependencies]` | no | package name to range text; used by `resolve --dev` and `why --dev` |

Any other table, or another key in `[package]`, is an error. A package may
not be listed in both dependency tables. Range values must be strings; they
are read by the resolver, not at load time.

## 2. Order

Requirements keep the order of the file: `[dependencies]` first, then
`[dev-dependencies]` when `--dev` is given. The order matters for the
resolution (`resolve.md`, section 2).

## 3. Errors

`load_manifest` fails with `DataError` (exit status 3) for a file that cannot
be read, is not TOML, or breaks section 1.
