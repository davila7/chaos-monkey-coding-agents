#!/bin/sh
# V-28: the conformance plan for codex-claude, run against the stub model (no model cost).
# Run from the repository root, with stub.py listening on the Docker host:
#   OUT=/tmp/v28 python3 docs/verification/V-28/stub.py &
#   W=<work dir> [CA=<extra CA bundle>] sh docs/verification/V-28/conformance.sh
set -u
rm -rf "$W" && mkdir -p "$W"
uv run python -m cmca_harbor.conformance plan --harness codex --version 0.163.0 --model claude-sonnet-5-5 \
  --build packages/injector-codex/dist/tt --out "$W/plan" --jobs "$W/jobs" > "$W/commands.txt"
ca=${CA:+--ak extra_ca_cert=$CA}
while IFS= read -r cmd; do
  cmd=$(echo "$cmd" | sed 's/cmca_harbor:ChaosCodex/v28_agent:StubCodex/')
  echo "+ $cmd" >> "$W/all.log"
  PYTHONPATH=docs/verification/V-28 OPENAI_API_KEY=unused uv run $cmd $ca \
    --agent-setup-timeout-multiplier 3 >> "$W/all.log" 2>&1 || echo "job failed: $cmd" >> "$W/all.log"
done < "$W/commands.txt"
echo "jobs: $(ls "$W/jobs" | wc -l), failed: $(grep -c 'job failed' "$W/all.log")"
