"""Command line (overview.md section 5)."""

import argparse
import json
import sys
from pathlib import Path

from .data import DataSet
from .errors import AgendaError
from .output import agenda_rows, event_doc, text_view


def _dump(value) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def run(ds: DataSet, out: Path) -> None:
    (out / "events").mkdir(parents=True, exist_ok=True)
    docs, errors = [], []
    for uid in ds.uids():
        try:
            doc = event_doc(ds.event(uid), ds.window)
        except AgendaError as e:
            errors.append({"event": uid, "error": f"{type(e).__name__}: {e}"})
            continue
        docs.append(doc)
        (out / "events" / f"{uid}.json").write_text(_dump(doc), encoding="utf-8")
    (out / "agenda.json").write_text(_dump(agenda_rows(docs)), encoding="utf-8")
    (out / "errors.json").write_text(_dump(errors), encoding="utf-8")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="agenda")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("expand", "show"):
        s = sub.add_parser(name)
        s.add_argument("uid")
        s.add_argument("--data", default="data")
    r = sub.add_parser("run")
    r.add_argument("--out", required=True)
    r.add_argument("--data", default="data")
    args = p.parse_args(argv)
    ds = DataSet(args.data)
    if args.cmd == "run":
        try:
            run(ds, Path(args.out))
        except AgendaError as e:
            print(f"{type(e).__name__}: {e}", file=sys.stderr)
            return 1
        return 0
    try:
        doc = event_doc(ds.event(args.uid), ds.window)
    except AgendaError as e:
        print(f"{type(e).__name__}: {e}", file=sys.stderr)
        return 1
    sys.stdout.write(_dump(doc) if args.cmd == "expand" else text_view(doc))
    return 0
