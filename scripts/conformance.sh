#!/usr/bin/env bash
# Runs SPEC 9.6 conformance for one harness version and writes its capability file.
#   scripts/conformance.sh <claude-code|pi|opencode> <version> <model id> [--gap type:class=reason ...]
# Needs Docker, uv, pnpm and ANTHROPIC_API_KEY. Each cell runs 3 times.
# CONFORMANCE_HARBOR_ARGS is appended to every `harbor run`. The default triples
# the agent setup timeout: on slow hosts, parallel harness installs pass 360 s.
set -euo pipefail
harness=$1 version=$2 model=$3
shift 3
jobs=${CONFORMANCE_JOBS:-jobs/conformance/$harness@$version}
harbor_args=${CONFORMANCE_HARBOR_ARGS---agent-setup-timeout-multiplier 3}
root=$(cd "$(dirname "$0")/.." && pwd)
cd "$root"

case $harness in
  claude-code) build=packages/injector-claude-code/dist/tt; harbor_model=$model ;;
  pi) build=packages/injector-pi/dist/tt; harbor_model=anthropic/$model ;;
  opencode) build=packages/injector-opencode/dist/tt; harbor_model=anthropic/$model ;;
  *) echo "unknown harness: $harness" >&2; exit 2 ;;
esac
: "${ANTHROPIC_API_KEY:?set ANTHROPIC_API_KEY}"
# Harbor's Pi agent treats any ANTHROPIC_BASE_URL as a custom endpoint (V-10).
unset ANTHROPIC_BASE_URL

pnpm install --frozen-lockfile
pnpm -r build
work=$jobs/plan
mkdir -p "$work"
uv run python -m cmca_harbor.conformance plan --harness "$harness" --version "$version" \
  --model "$harbor_model" --build "$build" --out "$work" --jobs "$jobs" > "$work.commands"
while IFS= read -r cmd; do
  echo "+ $cmd $harbor_args"
  eval "uv run $cmd $harbor_args" || echo "job failed: $cmd" >&2
done < "$work.commands"
uv run python -m cmca_harbor.conformance report --harness "$harness" --version "$version" --jobs "$jobs" "$@"
