#!/bin/sh
# V-28 round trip: one Codex session through the bridge to a scripted Messages API stand-in,
# in a container with no network, then check.py on the requests the stand-in received.
#   IMAGE=<V-02/Dockerfile image> OUT=<dir> sh docs/verification/V-28/roundtrip/run.sh   (after pnpm -r build)
set -eu
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../../../.." && pwd)
rm -rf "$OUT" && mkdir -p "$OUT"
docker run --rm --network none -v "$here:/work:ro" -v "$OUT:/out" \
  -v "$root/packages/responses-bridge/dist/tt/bridge:/bridge:ro" \
  -v "$root/configs/codex-claude.catalog.json:/catalog.json:ro" "$IMAGE" sh /work/session.sh
python3 "$here/check.py" "$OUT"
