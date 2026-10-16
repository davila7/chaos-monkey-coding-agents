"""Entry point.

    python -m frontdoor check  --config PATH
    python -m frontdoor routes --config PATH
    python -m frontdoor replay --config PATH --out DIR TRACE...
"""

import argparse
import sys

from frontdoor import __version__
from frontdoor.config import load_config
from frontdoor.errors import FrontdoorError, UsageError
from frontdoor.replay import replay


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise UsageError(message)


def build_parser() -> argparse.ArgumentParser:
    p = _Parser(prog="frontdoor", description="Replay request traces through the edge admission stages.")
    p.add_argument("--version", action="version", version=f"frontdoor {__version__}")
    sub = p.add_subparsers(dest="command", metavar="COMMAND", parser_class=_Parser)
    sub.required = True
    c = sub.add_parser("check", help="load a configuration and report problems")
    c.add_argument("--config", required=True)
    r = sub.add_parser("routes", help="print the route table of a configuration")
    r.add_argument("--config", required=True)
    rp = sub.add_parser("replay", help="replay traces and write decisions.jsonl and summary.json")
    rp.add_argument("--config", required=True)
    rp.add_argument("--out", required=True, metavar="DIR")
    rp.add_argument("traces", nargs="+", metavar="TRACE")
    return p


def main(argv=None) -> int:
    try:
        args = build_parser().parse_args(argv)
        config = load_config(args.config)
        if args.command == "check":
            print(f"ok: {len(config.routes)} routes, {len(config.tenants)} tenants")
        elif args.command == "routes":
            for route in config.routes:
                flag = " public" if route.public else ""
                print(f"{route.name}\t{route.prefix}\t{','.join(route.methods)}{flag}")
        else:
            n = replay(config, args.traces, args.out)
            print(f"replayed {n} requests")
        return 0
    except FrontdoorError as e:
        print(f"frontdoor: error: {e}", file=sys.stderr)
        return e.exit_status
