"""The tidecalc command line."""

from __future__ import annotations

import argparse
import os
import sys
import tomllib
from datetime import date

from tidecalc import __version__, catalog, plugins
from tidecalc.astro import constituents
from tidecalc.errors import TideError
from tidecalc.formats.base import Report
from tidecalc.predict import datum as datums
from tidecalc.predict.extrema import events
from tidecalc.predict.harmonic import Synthesizer
from tidecalc.timefmt import local_midnight

CONFIG_KEYS = ("lang", "format", "datum", "days")


def read_config(path: str | None) -> dict:
    path = path or os.environ.get("TIDECALC_CONFIG")
    if not path:
        return {}
    try:
        with open(path, "rb") as fh:
            doc = tomllib.load(fh)
    except OSError as exc:
        raise TideError(f"cannot read {path}: {exc.strerror}") from None
    except tomllib.TOMLDecodeError as exc:
        raise TideError(f"cannot parse {path}: {exc}") from None
    values = doc.get("options", {})
    unknown = sorted(set(values) - set(CONFIG_KEYS))
    if unknown:
        raise TideError(f"{path}: unknown setting(s) {', '.join(unknown)}")
    return values


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tidecalc", description="Tide predictions from harmonic constituents.")
    p.add_argument("--version", action="version", version=f"tidecalc {__version__}")
    p.add_argument("--lang", help="language of labels (en, de, fr, es, nl)")
    p.add_argument("--config", metavar="PATH", help="TOML file with an [options] table")
    sub = p.add_subparsers(dest="command", required=True, metavar="COMMAND")

    s = sub.add_parser("stations", help="list stations")
    s.add_argument("--region", choices=catalog.REGIONS)

    pr = sub.add_parser("predict", help="high and low waters, or a level series")
    pr.add_argument("station", help="station id or name")
    pr.add_argument("--start", required=True, type=date.fromisoformat, metavar="YYYY-MM-DD")
    pr.add_argument("--days", type=int)
    pr.add_argument("--format")
    pr.add_argument("--datum", choices=datums.DATUMS)
    pr.add_argument("--series", action="store_true", help="water level every --step minutes instead of highs and lows")
    pr.add_argument("--step", type=int, metavar="MIN", help="minutes between series values (60 when not given)")
    pr.add_argument("--output", metavar="FILE", help="write to FILE instead of stdout")

    sub.add_parser("formats", help="list output formats")

    c = sub.add_parser("constituents", help="harmonic constants of a station")
    c.add_argument("station")
    return p


def cmd_stations(args, conf, out) -> int:
    rows = catalog.in_region(args.region)
    width = max([len(r[1]) for r in rows] + [4])
    for ident, name, region, lat, lon in rows:
        out.write(f"{ident}  {name:<{width}}  {region:<8}{lat:9.4f}{lon:10.4f}\n")
    return 0


def cmd_predict(args, conf, out) -> int:
    days = args.days if args.days is not None else int(conf.get("days", 2))
    if not 1 <= days <= 31:
        raise TideError("--days must be between 1 and 31")
    step = args.step if args.step is not None else 60
    if not 5 <= step <= 180:
        raise TideError("--step must be between 5 and 180 minutes")
    fmt = plugins.get(args.format or conf.get("format", "text"))
    station = catalog.load(args.station)
    start = local_midnight(args.start, station.utc_offset_minutes)
    synth = Synthesizer(station, start)
    hours = days * 24
    if args.series:
        items = synth.series(hours - step / 60, step)
    else:
        items = events(synth, hours)
    datum = args.datum or conf.get("datum", "lat")
    items = datums.apply(items, station, datum)
    report = Report(station, args.start, days, datum, args.lang or conf.get("lang", "en"), tuple(items))
    text = fmt.render(report)
    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
    else:
        out.write(text)
    return 0


def cmd_formats(args, conf, out) -> int:
    for name, ep in plugins.available().items():
        try:
            desc = ep.load().DESCRIPTION
        except (ImportError, AttributeError):
            desc = "(cannot be loaded)"
        out.write(f"{name:<8}{desc}\n")
    return 0


def cmd_constituents(args, conf, out) -> int:
    station = catalog.load(args.station)
    for c in station.constituents:
        speed = constituents.speed(c.name) if constituents.known(c.name) else float("nan")
        out.write(f"{c.name:<5}{c.amplitude:8.3f} m{c.phase:8.1f} deg{speed:13.7f} deg/h\n")
    return 0


COMMANDS = {"stations": cmd_stations, "predict": cmd_predict, "formats": cmd_formats, "constituents": cmd_constituents}


def main(argv: list | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        conf = read_config(args.config)
        if args.lang is None and "lang" in conf:
            args.lang = conf["lang"]
        if args.lang is not None:
            from tidecalc import i18n

            i18n.messages(args.lang)
        return COMMANDS[args.command](args, conf, sys.stdout)
    except TideError as exc:
        sys.stderr.write(f"tidecalc: error: {exc}\n")
        return 2
