# pinset overview

pinset picks one version of every package a project needs, from a local
package index, and prints the result as a lock document. It is a library with
a small command line front end; other tools import `pinset.ranges`,
`pinset.version` and `pinset.resolver` directly.

## 1. Layout

| Path | What it holds |
|---|---|
| `pinset/cli.py` | argument parsing and the command table |
| `pinset/commands/` | one module per command (`conventions.md`, section 3) |
| `pinset/version.py` | versions and precedence (`versions.md`) |
| `pinset/ranges.py` | ranges (`ranges.md`) |
| `pinset/index.py`, `pinset/names.py` | the package index (`index.md`) |
| `pinset/manifest.py` | project manifests (`manifest.md`) |
| `pinset/resolver.py` | the resolution (`resolve.md`) |
| `pinset/output.py` | lock documents (`output.md`) |
| `data/index/` | the package index the team resolves against |
| `data/manifests/` | project manifests |
| `tests/` | unit tests |

## 2. Commands

    python -m pinset [--index DIR] resolve MANIFEST [--dev] [--format json|text]
    python -m pinset [--index DIR] show PACKAGE
    python -m pinset [--index DIR] match PACKAGE RANGE
    python -m pinset [--index DIR] check
    python -m pinset [--index DIR] why MANIFEST PACKAGE [--dev]
    python -m pinset [--index DIR] outdated MANIFEST [--dev]

`--index` defaults to `data/index`, relative to the working directory. Run
the commands from the directory that holds `pinset/`.

## 3. Release 2.0

Release 1.x understood two kinds of range: one version and a lower bound
(`>=`). Release 2.0 adds the range syntax that most manifests in
`data/manifests` and many index files already use: caret, tilde, wildcards,
hyphen ranges, comparator sets and `||`. The specification is `ranges.md`.
Until it lands, `check` reports every such range as `bad-range` and
`resolve` reports a problem for every requirement that uses one.

What does not change in 2.0:

- the index and manifest formats (`index.md`, `manifest.md`);
- the resolution order, the yanked rule and the problem codes
  (`resolve.md`);
- every output format (`output.md`);
- the public interface listed in `conventions.md`, section 4.

## 4. Status

See `changelog.md` for what has landed for 2.0 so far.
