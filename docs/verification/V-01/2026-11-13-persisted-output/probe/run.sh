#!/bin/bash
# usage: run.sh <mode> <command> <plugin_dir>
mode=$1; cmd=$2; plug=$3
echo "$mode" > /work/mode
node /work/fake-model.mjs 8787 /work/out/$mode.req.jsonl "$cmd" & sleep 1
cd /tmp && IS_SANDBOX=1 ANTHROPIC_BASE_URL=http://127.0.0.1:8787 ANTHROPIC_API_KEY=sk-fake CLAUDE_CODE_PLUGIN_DIRS=$plug CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 \
  timeout 120 claude -p hi --dangerously-skip-permissions --output-format json > /work/out/$mode.claude.json 2>/work/out/$mode.err
echo "exit $?"
kill %1
