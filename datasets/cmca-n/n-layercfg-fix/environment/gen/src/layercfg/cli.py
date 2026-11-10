"""Command line (overview.md section 4)."""

import argparse
import json
import sys
from pathlib import Path

from .data import DataSet
from .errors import ConfigError
from .report import resolve, summary_rows


def _dump(value) -> str:
    return json.dumps(value, indent=2) + "\n"


def run(ds: DataSet, out: Path) -> None:
    ds.schema  # a schema that cannot be read stops the whole run (overview.md 4.4)
    (out / "resolved").mkdir(parents=True, exist_ok=True)
    docs, errors = [], []
    for cid in ds.ids():
        try:
            doc = resolve(ds, cid)
        except ConfigError as e:
            errors.append({"config": cid, "error": f"{type(e).__name__}: {e}"})
            continue
        docs.append(doc)
        (out / "resolved" / f"{cid}.json").write_text(_dump(doc), encoding="utf-8")
    (out / "summary.json").write_text(_dump(summary_rows(docs)), encoding="utf-8")
    (out / "errors.json").write_text(_dump(errors), encoding="utf-8")


def get(ds: DataSet, cid: str, name: str):
    section, _, key = name.rpartition(".")
    settings = resolve(ds, cid)["settings"]
    if key not in settings.get(section.lower(), {}):
        raise ConfigError(f"{cid} has no setting {name}")
    return settings[section.lower()][key]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="layercfg")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("resolve")
    r.add_argument("id")
    r.add_argument("--data", default="data")
    g = sub.add_parser("get")
    g.add_argument("id")
    g.add_argument("name")
    g.add_argument("--data", default="data")
    a = sub.add_parser("run")
    a.add_argument("--out", required=True)
    a.add_argument("--data", default="data")
    args = p.parse_args(argv)
    ds = DataSet(args.data)
    try:
        if args.cmd == "run":
            run(ds, Path(args.out))
            return 0
        if args.cmd == "get":
            print(json.dumps(get(ds, args.id, args.name)))
            return 0
        doc = resolve(ds, args.id)
    except ConfigError as e:
        print(f"{type(e).__name__}: {e}", file=sys.stderr)
        return 1
    sys.stdout.write(_dump(doc))
    return 0
