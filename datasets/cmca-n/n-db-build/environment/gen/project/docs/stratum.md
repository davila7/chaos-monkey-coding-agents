# stratum

`stratum` builds an SQLite database from migrations, CSV seeds, views and checks, and upgrades
existing databases with the same migrations. It is a single Python file (`tools/stratum.py`)
that uses only the standard library.

## Commands

All commands read `stratum.toml` in the current directory unless `--config FILE` is given
before the command. Paths in the configuration are relative to the configuration file.

| Command | What it does |
|---|---|
| `build [--db FILE] [--dist DIR] [--to VERSION]` | Deletes the database file if it exists, creates a new one and runs the steps below in order. `--db` and `--dist` override `project.database` and `project.dist`. With `--to`, only migrations up to that version are applied, and no seeds, views, checks or exports. |
| `upgrade DATABASE` | Verifies the applied migrations, drops every view, applies the pending migrations, creates the views from the configuration and runs the checks. Seeds and exports are not touched. |
| `check DATABASE` | Runs the checks. |
| `status DATABASE` | Lists every migration as applied or pending. |

The tool stops at the first error, prints `stratum: error: ...` and exits with status 1.

## Build steps

1. **Migrations.** Files named `NNNN_name.sql` in `migrations.dir`, applied in version order.
   Each migration runs in its own transaction together with its row in the ledger table
   `schema_migrations (version, name, sha256)`. Foreign key enforcement is off while a migration
   runs, so tables can be rebuilt; when the migration's statements have run, every foreign key
   in the database is checked, and a violation fails the migration. On `upgrade`, the checksum
   of every applied migration must match its file.
2. **Seeds.** Each `[[seed]]` table, in the order listed, loads one CSV file into one table, in
   one transaction, with foreign key enforcement on. Every row is inserted as it is read, so by
   default a row must only reference rows already in the database. After the last seed every
   foreign key in the database is checked again.
3. **Views.** The files listed in `build.views`, in that order. Each file holds one
   `CREATE VIEW`; the view is queried once after it is created, so a view that refers to a
   missing table or column fails here.
4. **Checks.** Every file matched by the patterns in `build.checks` (sorted by name). Each file
   holds one `SELECT`; the check passes when it returns no rows. The build runs every check,
   prints up to five rows of each failing one, and fails if any check failed.
5. **Exports.** Each `[[export]]` runs its query and writes the result to `project.dist`.

## Configuration

```toml
[project]
database = "build/example.sqlite"   # default build output
dist = "dist"                        # export directory

[migrations]
dir = "migrations"

[build]
views = ["views/a.sql", "views/b.sql"]   # created in this order
checks = ["checks/*.sql"]                 # glob patterns

[[seed]]
table = "item"                 # target table (required)
file = "seeds/items.csv"       # CSV file with a header row (required)
encoding = "utf-8"             # any Python codec name; default utf-8
delimiter = ","                # default ","
null = [""]                    # field values stored as NULL; default [""]
deferred = false               # see below
columns = { item_id = "id" }   # table column = CSV header field; default: every header field
                               # is loaded into the column of the same name

[seed.map.status]              # value map for one column, applied after the null test
A = "active"                   # source value = stored value; values not in the map
                               # are stored unchanged

[[export]]
file = "items.csv"             # path under project.dist (required)
query = "SELECT * FROM item ORDER BY item_id"   # (required)
format = "csv"                 # csv (default) or json
```

`deferred = true` defers foreign key enforcement for that seed to the end of its transaction
(`PRAGMA defer_foreign_keys`): rows may reference rows that come later in the same file, and the
load fails at the end if any reference is still unresolved.

Field values are passed to SQLite as text; the column's type affinity converts them (`"12"`
in an `INTEGER` column is stored as the integer 12). Generated columns cannot be loaded.

## Exports

CSV exports are UTF-8 with a header row, `\n` line endings, fields quoted only when needed, and
NULL written as an empty field. JSON exports are a UTF-8 array of objects, one per row, keys in
column order, indented by two spaces, non-ASCII characters written as themselves, with a final
newline.
