"""Operator corrections to the state file (docs/operations.md 5).

    python3 tools/admin.py add PATH AMOUNT --ticket OPS-NNNN --by NAME [--root DIR]

Adds AMOUNT to the integer at PATH (for example members.M1012.balance_cents),
saves the state as a new revision with job "admin", and prints the line to
append to logs/ops.log.
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from spokehouse import ops, store  # noqa: E402
from spokehouse.timeutil import fmt_ts  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="admin.py")
    sub = parser.add_subparsers(dest="cmd", required=True)
    add = sub.add_parser("add")
    add.add_argument("path")
    add.add_argument("amount", type=int)
    add.add_argument("--ticket", required=True)
    add.add_argument("--by", required=True)
    add.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    args = parser.parse_args(argv)
    root = Path(args.root)
    state_file = root / "var" / "state.json"
    now = datetime.now(timezone.utc).replace(microsecond=0)
    state = store.load(state_file)
    out = store.save(state_file, ops.add(state, args.path, args.amount), job="admin", at=now, snapshots=root / "var" / "snapshots")
    print(f"{fmt_ts(now)} add {args.path} {args.amount:+d} ticket={args.ticket} by={args.by} "
          f"loaded={store.snapshot_name(state['meta'])} wrote={store.snapshot_name(out['meta'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
