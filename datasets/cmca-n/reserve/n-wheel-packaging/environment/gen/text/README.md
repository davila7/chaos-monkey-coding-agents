# tidecalc

Tide predictions from harmonic constituents. tidecalc computes high and low
waters, or the water level every few minutes, for the stations in its
catalogue, and writes them as text, tables, calendar files or web pages.

## Install

    pip install tidecalc

tidecalc has no runtime dependencies. The `plot` extra adds matplotlib for
charts and the `tz` extra adds tzdata for named time zones.

## Use

    tidecalc stations --region west
    tidecalc predict "Port Haven" --start 2026-03-01 --days 3
    tidecalc predict st-1234 --start 2026-03-01 --series --step 30 --format csv
    tidecalc --lang de predict st-1234 --start 2026-03-01 --datum msl
    tidecalc formats
    tidecalc constituents st-1234

Heights are in metres above chart datum (lowest astronomical tide), or above
mean sea level with `--datum msl`. Times are station local time.

A TOML file given with `--config` or `TIDECALC_CONFIG` can set options that
apply when the command line does not give them:

    [options]
    lang = "fr"
    format = "md"
    datum = "msl"
    days = 7

## Python API

    from datetime import date
    from tidecalc import catalog
    from tidecalc.predict.harmonic import Synthesizer
    from tidecalc.predict.extrema import events
    from tidecalc.timefmt import local_midnight

    station = catalog.load("st-1234")
    synth = Synthesizer(station, local_midnight(date(2026, 3, 1), station.utc_offset_minutes))
    for e in events(synth, 48):
        print(e.kind, e.time, round(e.height, 2))

`tidecalc.testing` has helpers for tests of code that uses tidecalc.

## Development

The build backend and how to build are described in docs/kiln.md; what a
release must contain is in docs/packaging.md. Tests run against an installed
wheel:

    python -m unittest discover -s tests -t .
