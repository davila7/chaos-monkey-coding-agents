"""Summarizes one offline trial: what each request to the stand-in model
declared and carried, and the tool calls in Harbor's trajectory.

    python3 show.py <requests.jsonl> <trial dir>
"""

import json
import sys
from pathlib import Path


def requests(path: Path) -> None:
    for i, line in enumerate(path.read_text().splitlines()):
        r = json.loads(line)
        b = r.get("body") or {}
        print(f"request {i}: {r['url']} model={b.get('model')}")
        print(f"  thinking={json.dumps(b.get('thinking'))} output_config={json.dumps(b.get('output_config'))}")
        print(f"  tools={[t.get('name') for t in b.get('tools') or []]}")
        for m in b.get("messages") or []:
            for c in m.get("content") if isinstance(m.get("content"), list) else []:
                if c.get("type") == "tool_result":
                    print(f"  tool_result is_error={c.get('is_error')} content={json.dumps(c.get('content'))[:700]}")


def trajectory(trial: Path) -> None:
    traj = json.loads((trial / "agent/trajectory.json").read_text())
    for step in traj.get("steps", []):
        results = {r.get("source_call_id"): r for r in ((step.get("observation") or {}).get("results") or [])}
        for call in step.get("tool_calls") or []:
            r = results.get(call.get("tool_call_id")) or {}
            print(f"trajectory call {call.get('function_name')} {json.dumps(call.get('arguments'))}")
            print(f"  observation={json.dumps(r.get('content'))[:700]}")
    events = trial / "artifacts/var/log/tt/events.jsonl"
    if events.exists():
        for line in events.read_text().splitlines():
            e = json.loads(line)
            print(f"gateway event tool={e.get('tool_name')} decision={e.get('decision')} type={e.get('type')} payload={e.get('payload_id')}")


if __name__ == "__main__":
    requests(Path(sys.argv[1]))
    trajectory(Path(sys.argv[2]))
