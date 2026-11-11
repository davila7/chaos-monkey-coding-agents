#!/bin/sh
# D-0053: the Codex injector with an `empty` fault forced on every command, for a command that
# ends during the write_stdin poll (script-yield.json), one that outlives the session
# (script-outlive.json) and one that ends before exec_command returns (script-quick.json).
# Prints the fault log, the injector's answers and the tool results the stub got back.
#   IMAGE=<V-02 image> OUT=<dir> sh docs/verification/V-02/yield-tt.sh   (after pnpm build)
set -eu
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../../.." && pwd)
for run in yield outlive quick; do
  rm -rf "${OUT:?OUT must be set}/$run" && mkdir -p "$OUT/$run"
  docker run --rm --network none -e SCRIPT=/work/script-$run.json -e HOOK=/work/hook-tt.sh \
    -v "$here:/work:ro" -v "$OUT/$run:/out" -v "$root/packages/injector-codex/dist/tt:/opt/tt:ro" \
    -v "$root/configs/codex-claude.catalog.json:/catalog.json:ro" "$IMAGE" sh /work/session.sh
  echo "== $run"
  python3 - "$OUT/$run" <<'P'
import json, sys
from pathlib import Path
d = Path(sys.argv[1])
for line in (d / "events.jsonl").read_text().splitlines():
    e = json.loads(line)
    print("  hook", e["hook_event_name"], e["tool_use_id"], "tool_response=" + json.dumps(e.get("tool_response")))
for line in (d / "answers.txt").read_text().splitlines():
    print("  answer", line or "(none)")
for line in (d / "tt-events.jsonl").read_text().splitlines() if (d / "tt-events.jsonl").exists() else []:
    e = json.loads(line)
    print("  log", json.dumps({k: e.get(k) for k in ("seq", "decision", "type", "tool_name", "capability", "of_seq", "reason")}))
last = json.loads((d / "requests.jsonl").read_text().splitlines()[-1])["body"]["input"]
for item in last:
    if item.get("type") == "function_call_output":
        print("  result", item["call_id"], json.dumps(item["output"]))
P
done
