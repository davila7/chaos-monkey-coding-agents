"""Prints the tool result each conformance probe call returned to the model (the trajectory observation).

    python3 visible.py <jobs dir> [attempt]
"""

import json
import sys
from pathlib import Path


def main() -> None:
    jobs = Path(sys.argv[1])
    attempt = sys.argv[2] if len(sys.argv) > 2 else "a0"
    for job in sorted(jobs.glob(f"conf-fxh-*-{attempt}")):
        for trial in sorted(p for p in job.iterdir() if (p / "agent/trajectory.json").exists()):
            steps = json.loads((trial / "agent/trajectory.json").read_text())["steps"]
            for step in steps:
                calls = {c["tool_call_id"]: c for c in step.get("tool_calls") or []}
                for r in (step.get("observation") or {}).get("results") or []:
                    call = calls.get(r["source_call_id"], {})
                    print(f"== {job.name} {trial.name.split('__')[0]} {call.get('function_name')} status={r.get('extra', {}).get('status')}")
                    print(r["content"])


if __name__ == "__main__":
    main()
