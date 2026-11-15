# Command line

    python -m deskstats COMMAND FOLDER [--since DAY] [--until DAY] [--format text|csv|json]

`FOLDER` is one site folder: `site.json` plus the exports described in
`sources.md`. A missing export counts as empty. Every command reads every
export, so a warning or an error in any of them shows for every command.

## Commands

| Command | One row per | Columns |
|---|---|---|
| `daily` | local day | `date`, `opened`, `closed`, `escalated`, `calls`, `call_s`, `chats`, `chat_s`, `staffed_h`, `note` |
| `tickets` | ticket, by opening time | `id`, `queue`, `opened`, `closed`, `resolved_s`, `escalations`, `first_escalation` |
| `calls` | call, by start | `start`, `queue`, `seconds` |
| `chats` | chat, by start | `id`, `queue`, `start`, `end`, `seconds` |
| `roster` | shift, by start | `agent`, `start`, `end`, `minutes` |

Times are written in the site's local time (the `utc_offset` of
`site.json`): `YYYY-MM-DD HH:MM:SS` in text and CSV, ISO 8601 with the
offset and any fraction of a second in JSON.

`daily` counts a ticket on the local day it was opened (`opened`) and on
the day it was closed (`closed`), an escalation, a call and a chat on the
day it starts, and a shift's minutes on each local day the shift covers.
`chat_s` is the length of the chats in whole seconds, `staffed_h` the
staffed hours, `note` the reason from `closures.txt` for a day the desk is
closed. Without `--since` and `--until` the rows run from the first to the
last day with data.

## Options

- `--since DAY`, `--until DAY`: local days (`YYYY-MM-DD`, or any form
  `date.fromisoformat` reads). A record is included when its time lies
  from `00:00:00` of `--since` to `23:59:59` of `--until`, both included.
  For `tickets` the time is the opening time, for `roster` the start of the
  shift. `daily` writes one row for every day from `--since` to `--until`.
- `--format`: `text` (default), `csv` or `json`.

## Errors

Exit status 2 with one line on standard error, `deskstats: error: ...`,
for a missing folder or `site.json`, a bad `utc_offset`, `--since` after
`--until`, and any line of `escalations.csv`, `calls.log`, `chats.jsonl` or
`roster.txt` that cannot be read. Bad times in `tickets.csv` and bad dates
in `closures.txt` are warnings: the row or line is left out and the run
goes on. An argument that is not a date is reported by the argument parser.
