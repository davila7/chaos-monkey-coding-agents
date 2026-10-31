import json,sys,os,time
ev=sys.argv[1]; d=json.load(sys.stdin)
open(f"/hooklog/{time.time_ns()}-{ev}.json","w").write(json.dumps(d))
cmd=json.dumps(d.get("tool_input",{}))
if ev=="pre":
    if "probe-deny-exit2" in cmd:
        sys.stderr.write("DENY-EXIT2-REASON"); sys.exit(2)
    if "probe-deny-json" in cmd:
        print(json.dumps({"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"DENY-JSON-REASON"}}))
elif ev in("post","postfail"):
    if "probe-post-block" in cmd:
        print(json.dumps({"decision":"block","reason":"REPLACED-BLOCK"}))
    if "probe-post-updated" in cmd:
        print(json.dumps({"hookSpecificOutput":{"hookEventName":"PostToolUse","updatedToolOutput":"REPLACED-UPDATED"}}))
    if "probe-post-exit2" in cmd:
        sys.stderr.write("REPLACED-EXIT2"); sys.exit(2)
sys.exit(0)
