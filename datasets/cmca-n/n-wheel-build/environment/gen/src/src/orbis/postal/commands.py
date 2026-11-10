"""The orbis-postal command line (3.x)."""

from __future__ import annotations

import argparse
import sys

from orbis.postal import __version__, countries, plugins, postcodes
from orbis.postal.errors import AddressError, PostalError
from orbis.postal.formatting import format_address
from orbis.postal.records import read_records
from orbis.postal.render import RenderOptions


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="orbis-postal", description="Format postal addresses by country.")
    parser.add_argument("--version", action="version", version=f"orbis-postal {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    fmt = sub.add_parser("format", help="format address records")
    fmt.add_argument("file", help="records as JSON lines, or CSV when the name ends in .csv")
    fmt.add_argument("-r", "--renderer", default="text", help="output renderer (default: text)")
    fmt.add_argument("--from", dest="origin", metavar="COUNTRY", help="sender country; its own addresses get no country line")
    abbr = fmt.add_mutually_exclusive_group()
    abbr.add_argument("--abbreviate", dest="abbreviate", action="store_true", default=None, help="abbreviate street names")
    abbr.add_argument("--no-abbreviate", dest="abbreviate", action="store_false", help="never abbreviate street names")

    chk = sub.add_parser("check", help="check the postcodes of address records")
    chk.add_argument("file")

    lst = sub.add_parser("countries", help="list the supported countries")
    lst.add_argument("--region", help="only this region")

    sub.add_parser("renderers", help="list the available renderers")
    return parser


def _format(args: argparse.Namespace, use_plugins: bool) -> tuple[str, int]:
    records = read_records(args.file)
    renderer = plugins.load(args.renderer, use_plugins)
    origin = countries.country(args.origin).code if args.origin else None
    items = []
    status = 0
    for address in records:
        try:
            items.append((address, format_address(address, origin=origin, abbreviate=args.abbreviate)))
        except AddressError as exc:
            print(f"orbis-postal: skipped: {exc}", file=sys.stderr)
            status = 1
    return renderer(RenderOptions(origin=origin)).render(items), status


def _check(args: argparse.Namespace) -> tuple[str, int]:
    out = []
    status = 0
    for address in read_records(args.file):
        try:
            fmt = countries.country_format(address.country)
        except AddressError:
            out.append(f"{address.id}\t{address.country}\tUNKNOWN-COUNTRY\t{address.postcode}")
            status = 1
            continue
        if not address.postcode:
            out.append(f"{address.id}\t{address.country}\tMISSING\t")
            status = 1
            continue
        shown = postcodes.display(address.postcode, fmt)
        if shown is None:
            out.append(f"{address.id}\t{address.country}\tINVALID\t{address.postcode}")
            status = 1
        else:
            out.append(f"{address.id}\t{address.country}\tOK\t{shown}")
    return "".join(line + "\n" for line in out), status


def _countries(args: argparse.Namespace) -> tuple[str, int]:
    known = countries.regions()
    if args.region and args.region not in known:
        raise AddressError(f"unknown region {args.region!r} (one of: {', '.join(known)})")
    rows = [c for c in countries.countries().values() if not args.region or c.region == args.region]
    return "".join(f"{c.code}\t{c.region}\t{c.name}\t{c.local_name}\n" for c in rows), 0


def _renderers(use_plugins: bool) -> tuple[str, int]:
    return "".join(f"{e.name}\t{e.origin}\t{e.target}\n" for e in plugins.entries(use_plugins)), 0


def main(argv: list[str] | None = None, *, plugins_enabled: bool = True) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "format":
            text, status = _format(args, plugins_enabled)
        elif args.command == "check":
            text, status = _check(args)
        elif args.command == "countries":
            text, status = _countries(args)
        else:
            text, status = _renderers(plugins_enabled)
    except PostalError as exc:
        print(f"orbis-postal: error: {exc}", file=sys.stderr)
        return exc.exit_status
    sys.stdout.write(text)
    return status
