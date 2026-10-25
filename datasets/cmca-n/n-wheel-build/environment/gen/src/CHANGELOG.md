# Changelog

## 3.2.0 (in preparation)

- `orbis.labels` (the `sheet` and `envelope` renderers) moved into this
  distribution from the separate orbis-labels project. It still registers
  its renderers as plugins, so third-party renderers and the label renderers
  are found the same way.
- Packaging moved from `setup.py` and `setup.cfg` to `pyproject.toml`. The
  release checklist is now docs/packaging.md.
- The version is kept only in `orbis/postal/_version.py`.
- New countries: Kenya, Morocco, Nigeria. Kosovo and the United Arab
  Emirates are drafts.
- Abbreviation table for Swedish street names.

## 3.1.4

- `check` prints the postcode as given for `INVALID` records.
- Envelope output escapes quotes in record ids.

## 3.1.0

- New `oneline` renderer.
- Postcode layouts: a format can list several layouts by length (United
  States ZIP and ZIP+4).

## 3.0.0

- Requires Python 3.11: format files are read with `tomllib`.
- The command line moved to `orbis.postal.commands` and gained the
  `check` and `renderers` commands and renderer plugins (entry point group
  `orbis.postal.renderers`). `orbis.postal.cli:main` stays importable for
  2.x scripts, without plugins, and will be removed in 4.0.
- `orbis` became a native namespace package shared by all Orbis
  distributions.

## 2.6.0

- Country data moved from Python modules to TOML files under `data/`.

## 2.5.1

- Fixed the Irish Eircode pattern.
