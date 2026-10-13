# Service configuration

Each service reads `/app/services/<service>/service.conf` when it starts. The deploy tool resolves that file, and everything it includes, at the start of a run.

## Syntax

- Lines are `key = value`. Blank lines and lines starting with `#` are ignored.
- `[name]` starts a section. Everything after it, up to the next section header or the end of the file, belongs to that section.
- Lines before the first section header are top level.
- The same section name can appear more than once in a file. Every block with that name applies, in file order.

## Reading order

- A file is read from top to bottom.
- `include = <path>` reads another file at that point. The path is relative to the directory of the file that contains the `include` line. The included file is read completely, including its own `include` lines, before reading continues with the line after the `include`.
- `include` lines are only honored at top level. An `include` line inside a section is ignored.
- Two variables are replaced in `include` paths: `${env}` by the environment of the deploy that starts the service, and `${host}` by the name of the host the service runs on (see host.md).
- When a key is set more than once, the value read last wins. Keys that come after an `include` line in the same file therefore override anything the included files set.
- Only files reached through `include` lines are read. Other files under /app/config have no effect on a service.
- The files under /app/config are the latest revision. A run may have used an older one; see config-history.md.

## Sections

- In `service.conf` sections are not used.
- In an included file, top-level keys apply to every service that reads the file. A `[name]` section applies only to the service whose `name` equals the section name; every other section is skipped.

## Listeners

Every service opens two TCP listeners, `main` first and then `admin`.

- `main` binds to `port_base + port_offset`.
- `admin` binds to `admin_port`.

## Enabled flag

`enabled = false` makes the deploy tool skip the service: it stops the old process if one is running and does not start a new one. When the key is never set the service is enabled.
