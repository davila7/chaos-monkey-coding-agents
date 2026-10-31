import json,sys,os,time
ev=sys.argv[1]; d=json.load(sys.stdin)
d["_env_MUSE_SESSION_ID"]=os.environ.get("MUSE_SESSION_ID"); d["_env_MUSE_THREAD_ID"]=os.environ.get("MUSE_THREAD_ID")
open(f"/hooklog/{time.time_ns()}-{ev}.json","w").write(json.dumps(d))
cmd=json.dumps(d.get("tool_input",{}))
tag={"bash":"FAIL","write_file":"WRITE","read_file":"READ","edit_file":"EDIT"}.get(d.get("tool_name"))
if ev in("post","postfail") and "probe" in cmd and tag:
    print(json.dumps({"decision":"block","reason":f"REPLACED-{tag}-{ev}"}))
sys.exit(0)
