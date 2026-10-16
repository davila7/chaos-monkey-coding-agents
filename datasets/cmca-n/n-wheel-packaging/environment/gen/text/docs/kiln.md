# kiln, the build backend

tidecalc is built by kiln, a small build backend kept in this repository
(`backend/kiln.py`). pyproject.toml points pip at it:

    [build-system]
    requires = []
    build-backend = "kiln"
    backend-path = ["backend"]

kiln needs nothing outside the standard library, so builds work offline.

## Building

From the repository root:

    python -m pip wheel --no-build-isolation --no-deps --no-index -w dist .
    python tools/build_sdist.py dist

The first command writes `dist/tidecalc-<version>-py3-none-any.whl`, the
second `dist/tidecalc-<version>.tar.gz`. To try a wheel, install it into a
fresh virtual environment:

    python -m venv /tmp/try
    /tmp/try/bin/pip install --no-index --no-deps dist/tidecalc-*.whl
    /tmp/try/bin/tidecalc --version

A wheel can also be built from an unpacked sdist with the same pip command,
run in the unpacked directory.

Output is reproducible: archive entries are sorted and every timestamp is
`SOURCE_DATE_EPOCH`, or 1980-01-01 when it is not set. Building the same tree
twice gives the same bytes.

## [project]

kiln reads the standard `[project]` table. Supported keys:

| Key | Meaning |
|---|---|
| `name` | Distribution name. The wheel and sdist file names use it lower-cased with `-` and `.` turned into `_`. |
| `version` | Static version. Leave it out and list `"version"` in `dynamic` to read it from a file instead (see `version-file`). |
| `description` | One-line summary (`Summary`). |
| `readme` | File whose text becomes the long description; `.md` files are marked as Markdown. |
| `requires-python` | Version specifier for supported Pythons (`Requires-Python`). pip refuses to install the wheel on other versions. |
| `license` | SPDX license expression, for example `"Apache-2.0"` or `"MIT OR GPL-2.0-only"` (`License-Expression`). |
| `license-files` | Globs, relative to the project root, of license files. Each match is recorded as `License-File` and copied to `<name>-<version>.dist-info/licenses/` in the wheel. A glob that matches nothing is an error. |
| `authors`, `maintainers` | Tables with `name` and `email`. |
| `keywords`, `classifiers`, `urls` | As in the packaging specifications. |
| `dependencies` | Runtime requirements (`Requires-Dist`). |
| `optional-dependencies` | Table of extra name to requirements. Each extra gives a `Provides-Extra` line and one `Requires-Dist` line per requirement with an `extra == "<name>"` marker. Extra names are lower-case letters, digits and single hyphens. |
| `scripts` | Console commands: `name = "package.module:function"`. pip creates an executable `name` that calls the function and exits with its return value. |
| `gui-scripts` | Like `scripts`, for GUI programs. |
| `entry-points` | Other entry point groups: `[project.entry-points."group.name"]` with `name = "package.module:object"` lines. kiln writes them to `entry_points.txt` without checking that the module or object exists. |
| `dynamic` | Keys filled in by the backend; kiln supports `version` only. |

An unknown key in `[project]` stops the build with an error that names it.

## [tool.kiln]

| Key | Meaning |
|---|---|
| `source` | Directory, relative to the project root, that holds the import packages. Fallback: `src`. |
| `version-file` | File, relative to the project root, with a line `__version__ = "X.Y.Z"`. Required when the version is dynamic. kiln reads the line with a regular expression; it does not import the file. |
| `exclude` | Globs of files to leave out of the wheel, matched against paths inside the wheel such as `tidecalc/cli.py`. They apply to modules and to package data. |
| `package-data` | Table of package name to a list of globs, relative to that package's directory, of non-Python files to ship: `tidecalc = ["data/*.csv"]`. |
| `sdist-include` | Globs, relative to the project root, of extra files for the sdist. |

An unknown key in `[tool.kiln]` stops the build.

### What goes into a wheel

1. Packages. kiln walks `source` and takes every directory that contains an
   `__init__.py` file and whose parent directories (up to `source`) are
   packages too. A directory without `__init__.py` is not a package, even if
   Python can import it from a checkout as a namespace package; kiln does not
   look inside it, so none of its files ship, and none of its
   subdirectories either.
2. Modules. Every `*.py` file directly inside a package, unless a glob in
   `exclude` matches its wheel path.
3. Package data. For each entry of `package-data`, every non-Python file
   below that package's directory (subdirectories included) that matches one
   of the globs, unless `exclude` matches its wheel path. Python files are
   never package data.
4. `.dist-info`: `METADATA`, `WHEEL`, `RECORD`, `entry_points.txt` when there
   are scripts or entry points, and `licenses/` for the license files.

`__pycache__` directories and `.pyc` files never ship.

### Globs

Globs use `/` as the separator on every platform.

- `*` matches any run of characters inside one path segment. It matches
  names that start with a dot too: `locales/*` matches `locales/.hidden`.
- `?` matches one character inside a segment.
- `**` as a whole segment matches any number of directories, zero included:
  `data/**/*.json` matches `data/a.json` and `data/x/y/b.json`. At the end
  of a glob it matches every file below: `data/**`.
- Matching is case-sensitive and covers the whole path.

## Source distributions

The sdist is `<name>-<version>.tar.gz` with a single top directory
`<name>-<version>/`. It holds `PKG-INFO`, `pyproject.toml`, the readme, the
license files, every file the wheel takes from `source` (at its path in the
repository), and every file matched by `sdist-include`. Nothing else is added:
a file the wheel build needs that is not in that list is missing from the
sdist.
