#!/bin/sh
# V-22 probes. Needs docker, python:3.12-slim tagged `py`, and the fx 0.0.13 archive extracted at $FX_DIR.
# Every run uses --network none; the model endpoint is stub.py on loopback, so no model is called.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
run() {  # name, entry script, extra docker args
  mkdir -p "$OUT/$1"
  docker run --rm --network none -e WAIT=40 $3 -v "$FX_DIR":/opt/fx:ro -v "$here":/p:ro -v "$OUT/$1":/out py sh "/p/$2"
}
run ask-caution run.sh "-e REVIEW=caution"
run ask-clear run.sh "-e REVIEW=clear"
run code run.sh "-e ACP_MODE=code"
run full-access run.sh "-e FX_PERMISSION_MODE=full-access"
run hooks hooks.sh "-e FX_PERMISSION_MODE=full-access"
