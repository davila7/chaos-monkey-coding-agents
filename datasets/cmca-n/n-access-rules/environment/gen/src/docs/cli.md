# docshelf command line

    python -m docshelf COMMAND WORKSPACE [ARGS] --as USER --at TIME

`WORKSPACE` is a folder with the four files below. `--as` names the user
who runs the command and `--at` the time it runs at, as
`YYYY-MM-DDTHH:MM`. Times in the workspace are in the same form and all
in the same zone; nothing reads the machine's clock.

## Commands

| Command | Arguments | Does |
|---|---|---|
| `list` | `[--format text\|csv\|json]` | the documents the user may open |
| `show` | `DOC` | one document and what the user may do with it |
| `edit` | `DOC --title TEXT` | changes the title in `docs.csv` |
| `share` | `DOC USER [--right read\|write] [--until TIME]` | adds a row to `grants.csv`, from `--at` to `--until` (or no end), with `granted_by` the user |
| `delete` | `DOC` | removes the document from `docs.csv` and its grants from `grants.csv` |
| `audit` | `[--format text\|csv\|json]` | for each document, who may open it and who may change it (admins only) |

`edit`, `share` and `delete` append one line to `activity.log` for every
attempt that gets past the argument checks:
`TIME USER ACTION DOC OUTCOME`, where the outcome is `ok`, `denied` or
`suspended`.

## Exit status

- 0: done.
- 2: bad arguments, a workspace file that cannot be read, an unknown user
  or document (`docshelf: error: ...`).
- 3: `show` of a document the user may not open
  (`docshelf: access denied: DOC`).
- 4: `edit`, `share`, `delete` or `audit` refused
  (`docshelf: permission denied: DOC`, `docshelf: account suspended: USER`,
  `docshelf: audit needs an active admin account`).

## Workspace files

`users.csv`: `user,role,team,status,suspended_until`. Roles in use are
`viewer`, `editor` and `admin`; the people team types them by hand.
`status` is `active` or `suspended`; `suspended_until` is a day
(`YYYY-MM-DD`) or empty.

`docs.csv`: `doc,title,owner,team,level`. `level` is `public` (everyone),
`team` (the members of `team`) or `private` (the owner and whoever holds a
grant).

`grants.csv`: `doc,user,right,from,until,granted_by`. `right` is `read` or
`write`; `doc` is a document id or `*` for every document; `from` and
`until` are times or empty.

`delegations.csv`: `from_user,to_user,from,until`. While a row is open,
`to_user` acts for `from_user` (cover during leave).
