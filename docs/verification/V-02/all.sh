#!/bin/sh
# V-02 and V-03: sessions with no hook output, a PostToolUse block, a PreToolUse deny, and the
# deny without the trust flag, in separate containers with no network, then the tool results
# Codex sent back to the model.
#   IMAGE=<image with node 22, python3 and @openai/codex@0.163.0> OUT=<dir> sh docs/verification/V-02/all.sh
set -eu
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../../.." && pwd)
for run in none block deny deny-untrusted; do
  mode=${run%-untrusted}
  untrusted=$([ "$run" = "$mode" ] || echo 1)
  rm -rf "$OUT/$run" && mkdir -p "$OUT/$run"
  docker run --rm --network none -e MODE=$mode -e UNTRUSTED=$untrusted -v "$here:/work:ro" -v "$OUT/$run:/out" \
    -v "$root/configs/codex-claude.catalog.json:/catalog.json:ro" "$IMAGE" sh /work/session.sh
done
python3 "$here/show.py" "$OUT"
