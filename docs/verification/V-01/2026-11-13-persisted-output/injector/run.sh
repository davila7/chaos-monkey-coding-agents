#!/bin/bash
# usage: run.sh <type>; runs Claude Code 2.1.289 with the built injector and the fake model
t=$1
mkdir -p /app /opt /logs/agent/tt && cp /work/big.conf /app/big.conf && cp -r /work/tt /opt/tt && cp /work/cfg/$t.json /opt/tt/config.json
node /work/fake-model.mjs 8787 /work/out/$t.requests.jsonl & sleep 1
cd /app && IS_SANDBOX=1 ANTHROPIC_BASE_URL=http://127.0.0.1:8787 ANTHROPIC_API_KEY=sk-fake CLAUDE_CODE_PLUGIN_DIRS=/opt/tt/cc CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 \
  timeout 120 claude -p go --dangerously-skip-permissions --output-format json > /work/out/$t.claude.json 2>/work/out/$t.stderr
echo "claude exit $?" > /work/out/$t.files.txt
for f in /root/.claude/projects/*/*/tool-results/*; do echo "== $(basename $f) $(wc -c < $f) bytes; last line: $(tail -n 1 $f)"; done >> /work/out/$t.files.txt
cp /logs/agent/tt/events.jsonl /work/out/$t.events.jsonl 2>/dev/null
kill %1
