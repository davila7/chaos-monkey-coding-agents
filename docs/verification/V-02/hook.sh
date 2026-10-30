#!/bin/sh
# Records each event; MODE=block replaces every result, MODE=deny refuses every call.
in=$(cat)
printf '%s\n' "$in" >> /out/events.jsonl
event=$(printf '%s' "$in" | python3 -c 'import json,sys;e=json.load(sys.stdin);print(e["hook_event_name"]);open("/out/transcript-at-post.jsonl","a").write("".join(l for l in open(e["transcript_path"]) if e["hook_event_name"]=="PostToolUse" and e["tool_use_id"] in l))')
case "$MODE:$event" in
  block:PostToolUse) printf '{"decision":"block","reason":"REPLACED"}' ;;
  deny:PreToolUse) printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"REFUSED"}}' ;;
esac
exit 0
