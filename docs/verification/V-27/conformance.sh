#!/bin/sh
# V-27 item (c): the conformance plan for fxh, run against the stub model (no model cost).
# Run from the repository root, with stub.py listening on the Docker host:
#   OUT=/tmp/v27 HOST=0.0.0.0 python3 docs/verification/V-27/stub.py &
#   W=<work dir> ARCHIVE=<fxh release archive> sh docs/verification/V-27/conformance.sh
set -u
rm -rf "$W" && mkdir -p "$W"
uv run python -m cmca_harbor.conformance plan --harness fxh --version 0.0.13-h1 --model anthropic/claude-sonnet-5.5 \
  --build packages/injector-fxh/dist/tt --out "$W/plan" --jobs "$W/jobs" > "$W/commands.txt"
while IFS= read -r cmd; do
  cmd=$(echo "$cmd" | sed 's/cmca_harbor:ChaosFxh/v27_agent:StubRelayFxh/')
  echo "+ $cmd" >> "$W/all.log"
  PYTHONPATH=docs/verification/V-27 AI_GATEWAY_API_KEY=dummy uv run $cmd --ak fxh_archive="$ARCHIVE" \
    --ae FX_GATEWAY_BASE_URL=http://127.0.0.1:8787 --ae FX_GATEWAY_CHAT_URL=http://127.0.0.1:8787/v1/chat \
    --agent-setup-timeout-multiplier 3 >> "$W/all.log" 2>&1 || echo "job failed: $cmd" >> "$W/all.log"
done < "$W/commands.txt"
echo "jobs: $(ls "$W/jobs" | wc -l), failed: $(grep -c 'job failed' "$W/all.log")"
