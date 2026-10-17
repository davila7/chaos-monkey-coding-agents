# Building the herbarium database

The herbarium specimen database is an SQLite file built from schema migrations, the export of
the collection system, views and checks. Release 2.0.0 is in preparation. This document is the
release contract: release engineering checks every rule below before a release is tagged.

## 1. Layout

| Path | Contents |
|---|---|
| `stratum.toml` | Build configuration (see `docs/stratum.md`). |
| `tools/stratum.py` | The build tool. It is shared with other projects and is not changed here; release engineering builds with its own copy of the same version. |
| `migrations/NNNN_name.sql` | Schema migrations, applied in version order. |
| `seeds/` | The export of the collection system, one CSV file per table. |
| `views/` | One `CREATE VIEW` per file. |
| `checks/` | Release checks, one query per file; a check passes when its query returns no rows. |
| `releases/1.6.0/herbarium.sqlite` | The database published as release 1.6.0. |
| `docs/schema.md` | The schema and the meaning of every column. |

Build output goes to `build/herbarium.sqlite` and `dist/`. A clean tree is the source tree
without `build/` and `dist/`.

## 2. Environment

The build runs with `python3` (3.12) and the SQLite library that Python links against in this
environment (3.40.1; `python3 -c 'import sqlite3; print(sqlite3.sqlite_version)'`). Every
migration, view and check must work with that version. Nothing is downloaded during the build.

## 3. Commands

    python3 tools/stratum.py build                 # fresh build: build/herbarium.sqlite, dist/
    python3 tools/stratum.py upgrade DATABASE      # bring an existing database to the current schema
    python3 tools/stratum.py check DATABASE        # run the checks

## 4. Release rules

1. **Fresh build.** `python3 tools/stratum.py build` succeeds on a clean tree: every migration,
   every seed, every view, every check and every export.
2. **Schema and content.** The database, its views and the exports match `docs/schema.md`.
3. **Released migrations are frozen.** Migrations 0001 to 0011 shipped with 1.x releases.
   Databases in use have recorded their checksums, and `stratum upgrade` refuses a database whose
   applied migrations no longer match the files. They are never edited, renamed or removed.
   Changes for 2.0.0 go into the unreleased migrations (0012 onward), which may be edited, or
   into new migrations.
4. **The export is used as delivered.** The files in `seeds/` are written by the collection
   system. They are not edited, re-encoded, sorted, split or copied elsewhere, and the
   configuration reads them from `seeds/`. The release is built from the export current on the
   release day: the same files and layout, with other and more specimens, taxa, collectors and
   sites, and any value the documentation allows.
5. **Encodings.** The collection system writes UTF-8. Files that still come from the old
   registry are written in Windows-1252 (code page 1252). Text is stored exactly as the source
   spells it: no replacement characters, no control characters, no characters lost or changed.
6. **Row order.** The collection system lists rows in its own order, which is not guaranteed
   to put a referenced row before the rows that reference it. The build must not depend on the
   order of rows in a seed file.
7. **Upgrade from 1.6.0.** `python3 tools/stratum.py upgrade` applied to a 1.6.0 database
   succeeds and gives the same schema as a fresh build (tables, columns, indexes, triggers,
   views) and the same rows as a fresh build from the export of the same collection.
   `releases/1.6.0/herbarium.sqlite` and `seeds/` describe the same collection. Upgrade a copy:
   the file under `releases/` is the published release. Release engineering upgrades the 1.6.0
   databases in use in the same way.
8. **Checks.** The checks in `checks/` state rules of `docs/schema.md`. They are not removed or
   weakened to make a build pass.
