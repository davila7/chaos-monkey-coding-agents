#!/bin/bash
# One Harbor trial of probe-s-read with the stand-in model, no model API.
#   harbor.sh <pi|oc> <task copy parent> <probes_s plan dir> <group> <jobs dir>
# The task copy is datasets/conformance-s/probe-s-read with the sandbox CA added
# to environment/Dockerfile and this service added to its compose file:
#   model:
#     image: tt-gateway:0.1.0
#     pull_policy: never
#     entrypoint: ["node", "/fake/fake-model.mjs"]
#     environment: { TOOL_SUFFIX: get_ticket, LOG: /log/requests.jsonl }
#     volumes: ["./fake:/fake:ro", "./fakelog:/log"]
# The plan dir comes from `python -m cmca_harbor.probes_s plan --config <pi-claude|opencode-claude>`.
set -u
kind=$1 tasks=$2 plan=$3 group=$4 jobs=$5
if [ "$kind" = pi ]; then
  # A base URL makes Harbor's Pi agent use a custom provider, which needs model_api.
  agent=cmca_harbor:ChaosPi; extra=(--ak version=1.0.3 --ak reasoning_effort=medium --ak model_api=anthropic-messages)
else
  agent=cmca_harbor:ChaosOpenCode; extra=(--ak version=1.18.35 --ak variant=medium)
fi
env TT_CONFIG_DIR="$plan/$group" TT_ATTEMPT=0 ANTHROPIC_BASE_URL=http://model:9000 ANTHROPIC_API_KEY=offline-dummy \
  uv run harbor run -p "$tasks" -a "$agent" -m anthropic/claude-sonnet-5-5 -k 1 -o "$jobs" \
  --job-name "e2e-$kind-$group" -y -i probe-s-read --ak attempt_index=0 "${extra[@]}" \
  --agent-setup-timeout-multiplier 3 -n 1
