"""tally count COLLECTION [--where FIELD=VALUE]...: number of matching records."""

from tally.textio import write_stdout
from tally.where import matches, parse_where

NAME = "count"
HELP = "count the records of a collection"


def register(p) -> None:
    p.add_argument("collection")
    p.add_argument("--where", action="append", metavar="FIELD=VALUE", help="keep records whose field equals VALUE (repeatable)")


def run(args, store) -> None:
    col = store.collection(args.collection)
    conditions = parse_where(args.where, col.schema)
    n = sum(1 for r in col.records() if matches(r, conditions))
    write_stdout(f"{n}\n")
