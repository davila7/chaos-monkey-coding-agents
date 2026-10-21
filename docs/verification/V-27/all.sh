#!/bin/sh
# V-27 items (a) and (b) on the Track N base image, no network, no model cost.
#   OUT=<dir> FX=<fx 0.0.13 binary> FXH=<fxh binary> sh all.sh
set -eu
here=$(cd "$(dirname "$0")" && pwd)
image=python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258
script=$(cat "$here/script.json")
mkdir -p "$OUT"
run() { # <name> <binary> [settings]
  docker run --rm --network none -e SCRIPT="$script" -e LOG=/out/$1/events.jsonl \
    -v "$here:/v27:ro" -v "$2:/opt/under-test/fx:ro" -v "$OUT:/out" "$image" \
    sh /v27/session.sh /opt/under-test/fx "/out/$1" ${3:-}
}
# (a) no `hooks` key: upstream fx and fxh, twice each.
run fx-1 "$FX"; run fx-2 "$FX"; run fxh-1 "$FXH"; run fxh-2 "$FXH"
# (b) a command that records every event and changes nothing.
cat > "$OUT/settings-log.json" <<'J'
{"hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": "python3 /v27/log.py"}]}],
           "PostToolUse": [{"hooks": [{"type": "command", "command": "python3 /v27/log.py"}]}]}}
J
run fxh-log "$FXH" /out/settings-log.json
python3 "$here/compare.py" "$OUT"
