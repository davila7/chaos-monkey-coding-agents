"""Command line: python -m docshelf COMMAND WORKSPACE [ARGS] --as USER --at TIME."""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from docshelf import audit, delete, edit, listing, render, share, show
from docshelf.errors import DataError, Denied
from docshelf.store import load, parse_time

FORMATS = ("text", "csv", "json")


def parse_at(text: str) -> datetime:
    try:
        return parse_time(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a time (YYYY-MM-DDTHH:MM): {text!r}") from None


def parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("workspace", type=Path)
    common.add_argument("--as", dest="user", required=True, help="the user who runs the command")
    common.add_argument("--at", type=parse_at, required=True, help="the time the command runs at")
    p = argparse.ArgumentParser(prog="docshelf", description="The team document shelf.")
    sub = p.add_subparsers(dest="command", required=True)
    c = sub.add_parser("list", parents=[common], help="documents you may open")
    c.add_argument("--format", choices=FORMATS, default="text")
    c = sub.add_parser("show", parents=[common], help="one document")
    c.add_argument("doc")
    c = sub.add_parser("edit", parents=[common], help="change a title")
    c.add_argument("doc")
    c.add_argument("--title", required=True)
    c = sub.add_parser("share", parents=[common], help="give someone a right on a document")
    c.add_argument("doc")
    c.add_argument("target")
    c.add_argument("--right", choices=["read", "write"], default="read")
    c.add_argument("--until", type=parse_at)
    c = sub.add_parser("delete", parents=[common], help="remove a document")
    c.add_argument("doc")
    c = sub.add_parser("audit", parents=[common], help="who may open and change what (admins)")
    c.add_argument("--format", choices=FORMATS, default="text")
    return p


def run(args) -> str:
    if not args.workspace.is_dir():
        raise DataError(f"{args.workspace}: not a folder")
    store = load(args.workspace)
    if args.user not in store.users:
        raise DataError(f"unknown user: {args.user}")
    if args.command == "list":
        return render.table(listing.HEADER, listing.rows(store, args.user, args.at), args.format)
    if args.command == "show":
        return render.fields(show.describe(store, args.user, args.doc, args.at))
    if args.command == "edit":
        return edit.edit(store, args.workspace, args.user, args.doc, args.title, args.at)
    if args.command == "share":
        return share.share(store, args.workspace, args.user, args.doc, args.target, args.right, args.until, args.at)
    if args.command == "delete":
        return delete.delete(store, args.workspace, args.user, args.doc, args.at)
    return render.table(audit.HEADER, audit.rows(store, args.user, args.at), args.format)


def main(argv: list | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        out = run(args)
    except Denied as e:
        print(f"docshelf: {e}", file=sys.stderr)
        return e.exit_code
    except DataError as e:
        print(f"docshelf: error: {e}", file=sys.stderr)
        return 2
    sys.stdout.write(out)
    return 0
