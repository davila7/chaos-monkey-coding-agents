#!/bin/sh
# Codex -> bridge -> mstub.py inside one container, with Codex configured as ChaosCodex does.
set -e
python3 /work/mstub.py & 
ANTHROPIC_BASE_URL=http://127.0.0.1:8788 ANTHROPIC_API_KEY=stub BRIDGE_USAGE_LOG=/out/usage.jsonl node /bridge/index.cjs > /out/bridge.log 2>&1 &
sleep 1
export CODEX_HOME=/tmp/ch; mkdir -p $CODEX_HOME /tmp/proj; cd /tmp/proj; echo hello > a.txt
cat > $CODEX_HOME/config.toml <<T
model_provider = "anthropic-bridge"
model_catalog_json = "/catalog.json"
model_reasoning_effort = "medium"
web_search = "disabled"
[model_providers.anthropic-bridge]
name = "anthropic-bridge"
base_url = "http://127.0.0.1:18080/v1"
wire_api = "responses"
supports_websockets = false
stream_idle_timeout_ms = 1800000
[features]
multi_agent = false
T
codex exec --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check --model claude-sonnet-5-5 --json -- "update the file" > /out/exec.jsonl 2> /out/stderr.txt || true
cat a.txt > /out/a.txt
