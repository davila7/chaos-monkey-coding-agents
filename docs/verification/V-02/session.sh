#!/bin/sh
# One Codex session against stub.py, inside the container. MODE: none, block or deny.
# UNTRUSTED=1 leaves out --dangerously-bypass-hook-trust (V-03).
set -e
trust=--dangerously-bypass-hook-trust
[ -n "${UNTRUSTED:-}" ] && trust=
mkdir -p /out
LOG=/out/requests.jsonl SCRIPT=/work/script.json python3 /work/stub.py & sleep 1
export CODEX_HOME=/tmp/ch; mkdir -p $CODEX_HOME /tmp/proj; cd /tmp/proj; echo hello > a.txt
cat > $CODEX_HOME/config.toml <<T
model_provider = "stub"
model_catalog_json = "/catalog.json"
web_search = "disabled"
[model_providers.stub]
name = "stub"
base_url = "http://127.0.0.1:8787/v1"
wire_api = "responses"
env_key = "STUB_KEY"
supports_websockets = false
[features]
hooks = true
multi_agent = false
[[hooks.PreToolUse]]
matcher = "^(Bash|apply_patch)\$"
[[hooks.PreToolUse.hooks]]
type = "command"
command = "/work/hook.sh"
timeout = 30
[[hooks.PostToolUse]]
matcher = "^(Bash|apply_patch)\$"
[[hooks.PostToolUse.hooks]]
type = "command"
command = "/work/hook.sh"
timeout = 30
T
STUB_KEY=unused codex exec --dangerously-bypass-approvals-and-sandbox $trust --skip-git-repo-check \
  --model claude-sonnet-5-5 --json -- "go" > /out/exec.jsonl 2> /out/stderr.txt || true
cat a.txt > /out/a.txt
