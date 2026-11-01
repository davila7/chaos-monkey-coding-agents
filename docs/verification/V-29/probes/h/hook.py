import json,sys,os,time
ev=sys.argv[1]; d=json.load(sys.stdin)
open(f"/hooklog/{time.time_ns()}-{ev}.json","w").write(json.dumps(d))
s=json.dumps(d)
if ev=="post" and d.get("tool_name")=="write_file" and "probe-nl" in s:
    print(json.dumps({"decision":"block","reason":"\n"}))
if ev=="post" and d.get("tool_name")=="write_file" and "probe-sp" in s:
    print(json.dumps({"decision":"block","reason":" "}))
if ev=="batch" and "probe-batch" in s:
    print(json.dumps({"decision":"block","reason":"REPLACED-BATCH"}))
sys.exit(0)
