#!/bin/bash
# Runs in the agent container of compose.yaml, with emit.py output and
# fake-model.mjs in /w. No model API: the only model endpoint is the local stand-in.
set -u
echo "== ChaosPi install command"
bash /w/pi-install.sh 2>&1 | tail -1
. ~/.nvm/nvm.sh
echo "== pi resolved packages"
(cd /tmp/pi-pinned && npm ls --all 2>/dev/null | grep -o '@earendil-works/[a-z-]*@[0-9.]*' | sort -u)
export PI_CODING_AGENT_DIR=/tmp/harbor-pi-agent
mkdir -p $PI_CODING_AGENT_DIR && cp /w/mcp.json $PI_CODING_AGENT_DIR/mcp.json
echo "== pi mcp list"
pi mcp list
echo "exit $?"
echo "== pi --thinking medium on the built-in anthropic provider, against the stand-in model"
PORT=9100 LOG=/w/pi-builtin-requests.jsonl node /w/fake-model.mjs & SRV=$!
sleep 1
echo '{"providers": {"anthropic": {"baseUrl": "http://127.0.0.1:9100"}}}' > $PI_CODING_AGENT_DIR/models.json
rm -f /w/pi-builtin-requests.jsonl
(cd /app && ANTHROPIC_API_KEY=offline-dummy timeout 120 pi --print --mode json --provider anthropic --model claude-sonnet-5-5 --thinking medium "Fetch ticket 501." </dev/null > /w/pi-builtin-stdout.jsonl 2>&1)
echo "exit $?"
kill $SRV
rm $PI_CODING_AGENT_DIR/models.json
unset PI_CODING_AGENT_DIR
echo "== OpenCode install (Harbor's command) and ChaosOpenCode config"
npm i -g opencode-ai@1.18.35 >/tmp/oc-install.log 2>&1 && opencode --version
bash /w/oc-config.sh
cat ~/.config/opencode/opencode.json
echo "== opencode mcp list"
(cd /app && opencode mcp list)
echo "exit $?"
