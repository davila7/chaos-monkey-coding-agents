"""tally schema COLLECTION: the fields of a collection."""

import json

from tally.fmt.table import render
from tally.textio import write_stdout

NAME = "schema"
HELP = "show the fields of a collection"


def register(p) -> None:
    p.add_argument("collection")
    p.add_argument("--json", action="store_true", help="print the schema as JSON")


def run(args, store) -> None:
    schema = store.collection(args.collection).schema
    if args.json:
        doc = {"collection": schema.collection, "key": schema.key,
               "fields": [{"name": f.name, "type": f.type, "scale": f.scale, "nullable": f.nullable} for f in schema.fields]}
        write_stdout(json.dumps(doc, indent=2) + "\n")
        return
    rows = []
    for f in schema.fields:
        t = f"decimal({f.scale})" if f.type == "decimal" else f.type
        rows.append([f.name, t, "yes" if f.nullable else "", "key" if f.name == schema.key else ""])
    write_stdout(render(["field", "type", "nullable", ""], rows))
