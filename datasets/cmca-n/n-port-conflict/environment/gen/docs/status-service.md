# Status service

`statusd` serves recorded runtime state for every host in the fleet. It does not start on its own.

Start it:

    /app/bin/statusd --background

It listens on 127.0.0.1:7311 and keeps running until the machine stops. Query it with `/app/bin/statusctl` or with plain HTTP GET requests (JSON responses).

| Command | HTTP | Answer |
|---|---|---|
| `statusctl hosts` | `/v1/hosts` | known hosts |
| `statusctl run <host> <deploy>` | `/v1/hosts/<host>/runs/<deploy>` | the revision the run requested and the revision the host actually loaded |
| `statusctl port <host> <port> --after <deploy>` | `/v1/hosts/<host>/ports/<port>?after=<deploy>` | whether a process was listening on the port right after that run finished on the host, and its pid |
| `statusctl port <host> <port>` | `/v1/hosts/<host>/ports/<port>` | the same, after the host's latest run |
| `statusctl proc <host> <pid>` | `/v1/hosts/<host>/procs/<pid>` | command line, start and exit time of a process |

Only apply runs are recorded. Dry runs, and runs that did not target the host, return an error.

## Loaded revision

At the start of an apply run each host fetches configuration revisions in order, up to the one in the record's `config_rev`. If a fetch fails, the host stops at the last revision it fetched and the run goes on with that revision. The deploy record only shows the requested revision; `statusctl run` shows the one the host used.
