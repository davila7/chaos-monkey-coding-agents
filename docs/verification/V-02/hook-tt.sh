#!/bin/sh
# Records each event, then hands it to the bundled Codex injector (D-0053) and records its answer.
in=$(cat)
printf '%s\n' "$in" >> /out/events.jsonl
out=$(printf '%s' "$in" | TT_CONFIG=/work/tt-config.json TT_STATE=/tmp/tt-state TT_LOG=/out/tt-events.jsonl \
  TT_DECIDE=/opt/tt/bin/tt-decide.cjs node /opt/tt/codex/index.cjs)
printf '%s\n' "$out" >> /out/answers.txt
printf '%s' "$out"
exit 0
