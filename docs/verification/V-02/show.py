"""Prints, per session, the tool results Codex sent to the model and the hook events it fired."""

import json
import sys
from pathlib import Path

out = Path(sys.argv[1])
for mode in ("none", "block", "deny", "deny-untrusted"):
    d = out / mode
    print(f"## {mode}")
    requests = [json.loads(x) for x in (d / "requests.jsonl").read_text().splitlines()]
    last = requests[-1]["body"]["input"]
    for item in last:
        if item.get("type") in ("function_call_output", "custom_tool_call_output"):
            print(f"{item['type']} {item['call_id']}: {json.dumps(item['output'])}")
    events = (d / "events.jsonl").read_text().splitlines() if (d / "events.jsonl").exists() else []
    print("events", len(events))
    for line in events:
        e = json.loads(line)
        keep = {k: e[k] for k in ("hook_event_name", "tool_name", "tool_input", "tool_use_id", "tool_response") if k in e}
        print("event", json.dumps(keep))
    if (d / "transcript-at-post.jsonl").exists():
        for line in (d / "transcript-at-post.jsonl").read_text().splitlines():
            item = json.loads(line).get("payload", {}).get("item") or {}
            if item:
                keep = {k: item.get(k) for k in ("type", "id", "exit_code", "duration", "status") if k in item}
                print("transcript item_completed", json.dumps(keep))
    print("a.txt", json.dumps((d / "a.txt").read_text()))
    print()
