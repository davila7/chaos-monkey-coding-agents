import json,sys,os,time
ev=sys.argv[1]; d=json.load(sys.stdin)
open(f"/hooklog/{time.time_ns()}-{ev}.json","w").write(json.dumps(d))
cmd=json.dumps(d.get("tool_input",{}))
if ev=="postfail":
    if "probe-f1" in cmd: sys.stderr.write("REPLACED-F1-EXIT2"); sys.exit(2)
    if "probe-f2" in cmd: print(json.dumps({"hookSpecificOutput":{"hookEventName":"PostToolUseFailure","updatedToolOutput":"REPLACED-F2-UPDATED"}}))
    if "probe-f3" in cmd: print(json.dumps({"decision":"block","reason":"REPLACED-F3-BLOCK","hookSpecificOutput":{"hookEventName":"PostToolUseFailure","additionalContext":"CONTEXT-F3"}}))
sys.exit(0)
