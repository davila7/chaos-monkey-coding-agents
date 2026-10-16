"""tally collections: the collections of the store and their record counts."""

from tally.fmt.table import render
from tally.textio import write_stdout

NAME = "collections"
HELP = "list the collections of the store"


def register(p) -> None:
    p.add_argument("--names-only", action="store_true", help="print one name per line")


def run(args, store) -> None:
    names = store.names()
    if args.names_only:
        write_stdout("".join(n + "\n" for n in names))
        return
    rows = [[n, str(store.collection(n).count()), str(len(store.collection(n).parts()))] for n in names]
    write_stdout(render(["collection", "records", "parts"], rows, right={1, 2}))
