# Service configuration

Each service reads `/app/services/<service>/service.conf` at startup.

- Lines are `key = value`. Lines starting with `#` are comments.
- `include = <path>` names another file, relative to the service directory. Included files are read after `service.conf`, in the order the `include` lines appear.
- An included file is split into sections such as `[gateway]`. A service only reads the section whose name equals its own `name`; other sections are ignored.
- When a key is set more than once, the last value read wins.
- A service without an `include` line reads only its own `service.conf`.
