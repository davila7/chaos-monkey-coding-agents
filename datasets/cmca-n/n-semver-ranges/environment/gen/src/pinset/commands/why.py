"""pinset why MANIFEST PACKAGE: how the resolution reached a package (docs/output.md, section 6)."""

from pinset.errors import UsageError
from pinset.index import load_index
from pinset.manifest import load_manifest
from pinset.resolver import chain, resolve

HELP = "print the chain of releases that brought a package in"


def add_arguments(p):
    p.add_argument("manifest")
    p.add_argument("package")
    p.add_argument("--dev", action="store_true", help="also resolve [dev-dependencies]")


def run(args, out) -> int:
    index = load_index(args.index)
    res = resolve(index, load_manifest(args.manifest), dev=args.dev)
    if args.package not in res.chosen:
        raise UsageError(f"{args.package} is not in the resolution")
    out.write(" -> ".join(chain(res, args.package)) + "\n")
    return 0
