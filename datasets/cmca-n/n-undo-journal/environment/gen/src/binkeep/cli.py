"""Entry point (docs/commands.md).

    python -m binkeep [--data DIR] [--by NAME] COMMAND ...
"""

import argparse
import sys

from binkeep import __version__, ops
from binkeep.context import Context
from binkeep.errors import BinkeepError, Refused, UsageError
from binkeep.report import entry_lines, log_line, stock_line

DEFAULT_DATA = "data"


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise UsageError("usage", message)


def _count(minimum: int):
    def parse(text: str) -> int:
        try:
            n = int(text, 10)
        except ValueError:
            raise argparse.ArgumentTypeError(f"not a whole number: {text}") from None
        if n < minimum:
            raise argparse.ArgumentTypeError(f"must be at least {minimum}: {text}")
        return n

    return parse


def _mutate(ctx: Context, result) -> list[str]:
    store, entry = result
    ctx.commit(store, [entry])
    return entry_lines(entry)


def cmd_receive(ctx, a):
    return _mutate(ctx, ops.receive(ctx, a.sku, a.bin, a.qty, packs=a.packs))


def cmd_issue(ctx, a):
    return _mutate(ctx, ops.issue(ctx, a.sku, a.qty))


def cmd_move(ctx, a):
    return _mutate(ctx, ops.move(ctx, a.sku, a.src, a.dst, a.qty))


def cmd_count(ctx, a):
    return _mutate(ctx, ops.count(ctx, a.sku, a.bin, a.qty))


def cmd_fix(ctx, a):
    return _mutate(ctx, ops.fix(ctx, a.sku, a.bin, a.qty))


def cmd_stock(ctx, a):
    store = ctx.store
    if a.sku is not None and a.sku not in ctx.items:
        raise Refused("unknown-sku", f"no item {a.sku}")
    skus = [a.sku] if a.sku is not None else store.skus()
    return [stock_line(s, c, store.qty(s, c)) for s in skus for c in store.bins_of(s)]


def cmd_log(ctx, a):
    return [log_line(e) for e in ctx.entries[-a.limit:]]


def build_parser() -> argparse.ArgumentParser:
    p = _Parser(prog="binkeep", description="Stock per bin, with an append-only journal.")
    p.add_argument("--version", action="version", version=f"binkeep {__version__}")
    p.add_argument("--data", default=DEFAULT_DATA, metavar="DIR", help=f"data directory (default {DEFAULT_DATA})")
    p.add_argument("--by", default="cli", metavar="NAME", help="who is making the change (default cli)")
    sub = p.add_subparsers(dest="command", metavar="COMMAND", parser_class=_Parser)
    sub.required = True

    s = sub.add_parser("receive", help="put stock into a bin")
    s.add_argument("sku")
    s.add_argument("bin")
    s.add_argument("qty", type=_count(1))
    s.add_argument("--packs", action="store_true", help="QTY counts packs, not units")
    s.set_defaults(run=cmd_receive)

    s = sub.add_parser("issue", help="take stock out, from bins in pick order")
    s.add_argument("sku")
    s.add_argument("qty", type=_count(1))
    s.set_defaults(run=cmd_issue)

    s = sub.add_parser("move", help="move stock between bins")
    s.add_argument("sku")
    s.add_argument("src", metavar="FROM")
    s.add_argument("dst", metavar="TO")
    s.add_argument("qty", type=_count(1))
    s.set_defaults(run=cmd_move)

    for name, run, help_text in (("count", cmd_count, "record a cycle count"),
                                 ("fix", cmd_fix, "correct a quantity by hand")):
        s = sub.add_parser(name, help=help_text)
        s.add_argument("sku")
        s.add_argument("bin")
        s.add_argument("qty", type=_count(0))
        s.set_defaults(run=run)

    s = sub.add_parser("stock", help="print stock per bin")
    s.add_argument("sku", nargs="?")
    s.set_defaults(run=cmd_stock)

    s = sub.add_parser("log", help="print the latest journal entries")
    s.add_argument("--limit", type=_count(1), default=10)
    s.set_defaults(run=cmd_log)
    return p


def main(argv=None, out=None) -> int:
    out = out if out is not None else sys.stdout
    try:
        args = build_parser().parse_args(argv)
        lines = args.run(Context(args.data, args.by), args)
    except BinkeepError as e:
        print(f"binkeep: error: {e.code}: {e}", file=sys.stderr)
        return e.exit_status
    for line in lines:
        print(line, file=out)
    return 0
