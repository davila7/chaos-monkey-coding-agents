#!/bin/sh
# Runs one scripted fx session inside a container, against stub.py on loopback.
#   session.sh <fx binary> <out dir> [settings.json]
# Same workspace (/app), home (/root) and files on every run, so request bytes
# can be compared across binaries.
set -u
FX=$1 OUT=$2 SETTINGS=${3:-}
mkdir -p "$OUT" /app /root/.fx
[ -n "$SETTINGS" ] && cp "$SETTINGS" /root/.fx/settings.json
cd /app
printf 'hello\nworld\n' > a.txt
seq 1 40 | sed 's/^/row /' > rows.txt
OUT=$OUT python3 /v27/stub.py &
stub=$!
python3 -c 'import socket,time
for _ in range(50):
    try: socket.create_connection(("127.0.0.1", 8787)).close(); break
    except OSError: time.sleep(0.1)'
HOME=/root AI_GATEWAY_API_KEY=dummy FX_MODEL=anthropic/claude-sonnet-5.5 FX_SKIP_ONBOARDING=1 FX_AUTO_UPGRADE=0 FX_DISABLE_KEYCHAIN=1 \
FX_GATEWAY_BASE_URL=http://127.0.0.1:8787 FX_GATEWAY_CHAT_URL=http://127.0.0.1:8787/v1/chat \
  timeout 120 "$FX" ask --full-access --json -- "Look at the files in this folder." > "$OUT/stdout.json" 2> "$OUT/stderr.txt"
echo "exit=$?" > "$OUT/exit.txt"
kill $stub
cp -r /root/.fx/sessions "$OUT/sessions" 2>/dev/null || true
