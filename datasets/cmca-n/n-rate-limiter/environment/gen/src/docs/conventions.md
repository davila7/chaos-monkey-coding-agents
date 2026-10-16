# Code conventions

## 1. General

- Standard library only. Python 3.12.
- Times inside the package are integers: milliseconds since the Unix epoch
  (`timeutil.parse_ts`). Configuration durations for the upstream client are
  the one exception (`config/durations.py` returns seconds as a float, which
  is what the upstream client takes).
- Small modules, named after what they do. A helper used by one stage lives
  next to that stage or in its own subpackage.

## 2. Errors and exit statuses

| Class | Exit status | Used for |
|---|---|---|
| `UsageError` | 2 | a wrong command line |
| `ConfigError` | 2 | a configuration that breaks a rule of `config.md` or of the note of a section |
| `TraceError` | 3 | a trace file that cannot be read or holds a line that is not a request |

`frontdoor.cli.main` prints `frontdoor: error: <message>` on standard error
and returns the status. A command that fails writes nothing: configurations
are loaded and checked completely before any trace is read, and `replay`
writes its output files only after the last request.

## 3. Configuration sections

Each top-level table or array of tables in a configuration file is a section.
A section is added in three steps:

1. A module under `frontdoor/config/` with a `parse(value)` function that
   checks the raw TOML value and returns the parsed form, raising
   `ConfigError` for anything the section's rules do not allow. Unknown keys
   inside a section are errors.
2. An entry in `SECTIONS` in `frontdoor/config/sections.py`. A section that
   is not listed there makes `load_config` fail with "unknown section".
3. When a rule relates two sections (for example a name that must refer to a
   route), a check function in `CHECKS` in the same file. Checks run after
   every section is parsed and get the `Config`.

Stages read their sections with `config.section(name)`, which returns the
parsed value or None when the file has no such section.

## 4. Stages

A stage is a module under `frontdoor/stages/` with:

- `NAME`;
- `setup(config)`: called once per replay, before the first request; it
  returns the stage's state, which lives for the whole replay (every trace
  file of one `replay` command);
- `handle(ctx, state)`: called for each request that reaches the stage. It
  returns None to pass the request on, or an HTTP status to answer it. It
  may add response headers to `ctx.headers`;
- optionally `summary(state)`: called once after the last request; it returns
  a dict whose entries are added to `summary.json` (`output.md`, section 3).

The stage list is `STAGES` in `frontdoor/stages/__init__.py`.

## 5. Tests

Tests live under `tests/`, one module per area. They build small
configurations and traces in temporary directories (`tests/support.py`) and
run the commands through `frontdoor.cli.main`.
