"""Minimal ACP client: advertises fs and terminal capabilities, logs every message, answers client-side requests."""
import json, os, subprocess, threading

log = open("/out/acp.jsonl", "w")
p = subprocess.Popen(["/opt/fx/fx", "acp", "--log-file", "/out/fx-acp.log"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, cwd="/w")
results = {}


def send(obj):
    log.write(json.dumps({"dir": "out", "msg": obj}) + "\n"); log.flush()
    p.stdin.write((json.dumps(obj) + "\n").encode()); p.stdin.flush()


def reader():
    for line in p.stdout:
        msg = json.loads(line)
        log.write(json.dumps({"dir": "in", "msg": msg}) + "\n"); log.flush()
        if "method" in msg and "id" in msg:  # a request from fx to the client
            m = msg["method"]
            if m == "fs/read_text_file":
                send({"jsonrpc": "2.0", "id": msg["id"], "result": {"content": "CLIENT-INTERCEPTED\n"}})
            elif m == "session/request_permission":
                send({"jsonrpc": "2.0", "id": msg["id"], "result": {"outcome": {"outcome": "selected", "optionId": msg["params"]["options"][0]["optionId"]}}})
            else:
                send({"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32601, "message": "client stub: " + m}})
        elif msg.get("id") in results:
            results[msg["id"]]["msg"] = msg
            results[msg["id"]]["e"].set()


def call(i, method, params, wait=30.0):
    results[i] = {"e": threading.Event()}
    send({"jsonrpc": "2.0", "id": i, "method": method, "params": params})
    results[i]["e"].wait(wait)
    return results[i].get("msg")


threading.Thread(target=reader, daemon=True).start()
call(1, "initialize", {"protocolVersion": 1, "clientCapabilities": {"fs": {"readTextFile": True, "writeTextFile": True}, "terminal": True}})
sid = call(2, "session/new", {"cwd": "/w", "mcpServers": []})["result"]["sessionId"]
if os.environ.get("ACP_MODE"):
    call(3, "session/set_mode", {"sessionId": sid, "modeId": os.environ["ACP_MODE"]})
r = call(4, "session/prompt", {"sessionId": sid, "prompt": [{"type": "text", "text": "Read a.txt and run `cat a.txt`."}]}, wait=float(os.environ.get("WAIT", "40")))
print("prompt result:", json.dumps(r)[:600])
p.terminate()
