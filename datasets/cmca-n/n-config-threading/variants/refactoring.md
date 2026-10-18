# Passing settings explicitly

quoter keeps its configuration in one process-wide object,
`quoter.settings.SETTINGS`, which the command line fills in with
`configure()` and library code reads wherever it needs a value. The pricing
service is going to run quoter as a library inside one long-running process
that quotes for many customers, each with its own settings, one request after
another. With a process-wide object that cannot work: one customer's settings
leak into the next customer's prices.

This change replaces the process-wide object with settings values that are
passed explicitly to the code that needs them. It is a refactor: what the
command line prints does not change.

## 1. The Settings value

1.1 `Settings` keeps its fields, their types and their fallback values, and
becomes immutable: assigning to a field of a `Settings` raises
`dataclasses.FrozenInstanceError`. Two `Settings` with equal fields are equal
and have the same hash.

1.2 `quoter.settings` no longer has `SETTINGS`, `configure`, `reset` or
`current`. It gains one function:

    make(**values) -> Settings

which returns a new `Settings` with the fallback values, then each given value
converted and checked by `parse_value`. Any bad value raises `SettingsError`.
`make()` with no arguments equals `Settings()`.

1.3 `parse_value`, `read_file`, `read_env`, `FIELD_TYPES`, `CHOICES`,
`CARRIER_NAMES` and `ENV_PREFIX` keep their names, signatures and behavior.
`make` checks exactly what `parse_value` checks and nothing more; settings
with a small format of their own are still read when they are first needed
(see docs/settings.md).

## 2. Passing settings

2.1 A function or method that needs a setting, itself or through anything it
calls, takes the settings as a parameter named `conf`. It is the first
parameter, after `self` or `cls` where there is one.

2.2 A function that needs no setting keeps its signature.

2.3 A value that depends on a setting and was read as an attribute becomes a
method or function that takes `conf`.

2.4 The command line builds one `Settings` with `make` from the sources listed
in docs/settings.md, in the same priority order, and passes it down to the
command it runs.

## 3. No hidden settings

3.1 Outside `quoter/settings.py`, no module keeps a `Settings` value in a
global variable, a class attribute, the fallback value of a parameter or a
closure.

3.2 Nothing reads a setting while a module is being imported. Importing any
quoter module, in any order, before or after settings are made, gives the
same results.

3.3 Results that depend on settings may still be kept for reuse, but a kept
result is reused only for settings equal to those it was computed with.
Settings values may be created and dropped freely; a result must never be
reused for different settings because of object identity.

3.4 The results for one `Settings` never depend on which other `Settings` were
used earlier in the same process.

## 4. Library entry points

These are the functions other code calls. After the change they have exactly
these signatures (parameter names, their order and fallback values):

| Function | Signature |
|---|---|
| `quoter.settings.make` | `make(**values)` |
| `quoter.services.quotes.make_request` | `make_request(conf, origin, dest, weight, dims=None, residential=False, declared_v2=None)` |
| `quoter.services.quotes.quote_all` | `quote_all(conf, req, carrier=None, service=None)` |
| `quoter.services.quotes.cheapest` | `cheapest(conf, req)` |
| `quoter.services.batch.run_batch` | `run_batch(conf, path)` |
| `quoter.output.render.render_quotes` | `render_quotes(conf, quotes, request, fmt)` |
| `quoter.output.render.render_batch` | `render_batch(conf, result, fmt)` |
| `quoter.geo.zones.zone_for` | `zone_for(conf, origin, dest)` |
| `quoter.geo.zones.zones_from` | `zones_from(conf, origin)` |
| `quoter.carriers.registry.enabled` | `enabled(conf)` |
| `quoter.services.cache.stats` | `stats()` |
| `quoter.cli.main` | `main(argv=None)` |

The objects they return (`QuoteRequest`, `Quote`, `BatchResult` and so on)
keep their fields.

## 5. Behavior

5.1 For every command, option, config file and environment variable, the
command line writes the same bytes to stdout and stderr and exits with the
same status as before, `--debug` output included.

5.2 Calling the entry points with a `Settings` made from some values gives the
same results as the command line run with the same values. This holds for any
values, not only the ones in /app/samples and /app/tests.

5.3 Behavior that looks odd is kept. This change does not fix, validate or
round anything differently from before; anything that looks like a bug is
out of scope and gets its own change.

## 6. Tests

The tests in /app/tests use the old API (`configure`, `reset`). Move them to
the new one, keeping what each test checks. From /app:

    python -m unittest discover -s tests -t .
