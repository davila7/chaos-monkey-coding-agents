"""Compares the request bytes of the V-27 sessions and summarizes the recorded events.

    python3 compare.py <out dir>

Three values change on every run, with either binary: the session id fx sends
in headers, the random part of shell replay handles, and shell `duration_ms`.
They are replaced with placeholders. The title request and the model list
request run concurrently, so requests are compared as a sorted list. Everything
else must be byte-identical.
"""

import json
import re
import sys
from pathlib import Path

REPLAY = re.compile(r"fx-command-replay-[0-9a-f]+-[0-9a-f]+\.bin")
DURATION = re.compile(r'(\\"duration_ms\\":)\d+')


def requests(run: Path) -> list[dict]:
    reqs = [json.loads(p.read_text()) for p in sorted(run.glob("req-*.json"), key=lambda p: int(p.stem.split("-")[1]))]
    out = []
    for r in reqs:
        sid = r["headers"].get("x-session-id") or r["headers"].get("X-Session-Id")
        def norm(s: str) -> str:
            s = REPLAY.sub("fx-command-replay-<id>.bin", s)
            s = DURATION.sub(r"\1<ms>", s)
            return s.replace(sid, "<session>") if sid else s
        headers = {k.lower(): norm(v) for k, v in r["headers"].items() if k.lower() != "content-length"}
        out.append({"method": r["method"], "path": r["path"], "headers": headers, "body": norm(r["body"])})
    return sorted(out, key=lambda r: (r["method"], r["path"], r["body"]))


def main() -> int:
    out = Path(sys.argv[1])
    base = requests(out / "fx-1")
    ok = True
    for name in ("fx-2", "fxh-1", "fxh-2", "fxh-log"):
        other = requests(out / name)
        same = len(other) == len(base) and all(a == b for a, b in zip(base, other))
        ok &= same
        print(f"(a) {name} vs fx-1: {len(other)} requests, {'identical' if same else 'DIFFERENT'} after normalization")
    events = [json.loads(line) for line in (out / "fxh-log/events.jsonl").read_text().splitlines()]
    print(f"(b) {len(events)} events")
    for e in events:
        fields = sorted(e)
        extra = f" tool_failed={e['tool_failed']}" if "tool_failed" in e else ""
        print(f"    {e['hook_event_name']:<11} {e['tool_name']:<10} {e['tool_use_id']:<7} fields={','.join(fields)}{extra}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
