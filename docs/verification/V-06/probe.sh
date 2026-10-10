#!/bin/bash
# usage: probe.sh <name> <type|none> <tool> '<input json with $WS>' [plugin url]
set -u
B=/w/runs/$1; rm -rf $B; mkdir -p $B/ws $B/xdg/opencode $B/tt
printf 'line one\nline two\nline three\n' > $B/ws/input.txt
BASE_CFG="$(cat /w/base.json)" node /w/cfg.mjs $B/tt/config.json ${2/none/deny}
INPUT=${4//\$WS/$B/ws}
echo "[{\"name\":\"$3\",\"input\":$INPUT}]" > $B/script.json
PLUGIN="\"plugin\": [\"${5:-file:///w/tt/oc/index.js}\"],"
[ "$2" = none ] && PLUGIN=''
for i in 1 2 3; do
  PORT=$((20000 + RANDOM % 10000))
  node /w/server.mjs $PORT $B/script.json $B/requests.jsonl & SRV=$!
  sleep 0.5
  echo "{ $PLUGIN \"provider\": { \"anthropic\": { \"npm\": \"@ai-sdk/anthropic\", \"models\": { \"claude-sonnet-4-5\": { \"name\": \"m\", \"tool_call\": true } }, \"options\": { \"baseURL\": \"http://127.0.0.1:$PORT/v1\", \"apiKey\": \"x\" } } } }" > $B/xdg/opencode/opencode.json
  (cd $B/ws && XDG_CONFIG_HOME=$B/xdg XDG_DATA_HOME=$B/data XDG_STATE_HOME=$B/state OPENCODE_FAKE_VCS=git OPENCODE_DISABLE_MODELS_FETCH=1 \
    TT_CONFIG=$B/tt/config.json TT_STATE=$B/tt/state TT_LOG=$B/tt/events.jsonl TT_DECIDE=/w/tt/bin/tt-decide.cjs \
    timeout 45 opencode --model=anthropic/claude-sonnet-4-5 run --format=json --dangerously-skip-permissions -- go </dev/null > $B/stdout.jsonl 2> $B/stderr.txt)
  kill $SRV
  grep -q tool_result $B/requests.jsonl 2>/dev/null && break
done
python3 /w/show.py $B
