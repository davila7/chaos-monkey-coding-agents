#!/usr/bin/env bash
# Builds the Track S service images that datasets/cmca-s compose files reference
# (pull_policy: never). Rebuild after changing mcp-fault-proxy or mock-services.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
cd "$root"
pnpm --filter @cmca/fault-engine --filter @cmca/mock-services --filter @cmca/mcp-fault-proxy build
version=$(node -p "require('./packages/mcp-fault-proxy/package.json').version")
docker build -q -t "tt-gateway:$version" packages/mcp-fault-proxy
version=$(node -p "require('./packages/mock-services/package.json').version")
docker build -q -t "tt-tickets:$version" packages/mock-services
