# Status service

`statusd` serves recorded runtime state for every host in the fleet. It does not start on its own.

Start it:

    /app/bin/statusd --background

It listens on 127.0.0.1:7311 and keeps running until the machine stops. Query it with `/app/bin/statusctl` or with plain HTTP GET requests (JSON responses). `statusctl <command> --help` lists the options of each command.

| Command | HTTP | Answer |
|---|---|---|
| `statusctl hosts` | `/v1/hosts` | known hosts |
| `statusctl run <host> <deploy>` | `/v1/hosts/<host>/runs/<deploy>` | what one apply run did on one host |
| `statusctl port <host> <port> --from <time> --to <time> [--page <n>]` | `/v1/hosts/<host>/ports/<port>/events?from=<time>&to=<time>&page=<n>` | bind and release events on one port of one host within a time window |
| `statusctl proc <host> <pid>` | `/v1/hosts/<host>/procs/<pid>` | one process |

## Runs

The answer for a run has `requested_rev`, `loaded_rev`, `note`, `started_at` and `finished_at` (UTC, when the run began and finished handling that host) and `failed_pids`, the processes that run started on the host and that exited during startup.

Only apply runs are recorded, and only on hosts the run handled. Dry runs, and hosts a run did not reach, return an error.

At the start of an apply run each host fetches configuration revisions in order, up to the one in the record's `config_rev`. If a fetch fails, the host stops at the last revision it fetched and the run goes on with that revision. The deploy record only shows the requested revision.

## Port events

A `bind` event is written when a process starts listening on a port, a `release` event when it stops listening. A port is held by a process from its `bind` until its next `release`. There is no query for the holder at a given moment; read the events.

- Times are ISO 8601 and must carry `Z` or a UTC offset. Answers use UTC with milliseconds.
- `from` is inclusive and `to` is exclusive. A window may span at most 72 hours.
- Events are returned oldest first, 4 per page. The answer gives `page` and `pages`; ask for the next page with `--page`.

## Processes

The answer for a process has its command line, `started_at`, `exited_at` (null while it runs) and `exit_status`.
