import json, http.server, itertools
n = itertools.count()
state = {"main": 0}
def sse(parts):
    return "".join(f"data: {json.dumps(p)}\n\n" for p in parts).encode()
USAGE = {"inputTokens": {"total": 10, "noCache": 10, "cacheRead": 0, "cacheWrite": 0}, "outputTokens": {"total": 5, "text": 5, "reasoning": 0}}
def finish(reason):
    return {"type": "finish", "finishReason": {"unified": reason, "raw": reason}, "usage": USAGE}
class H(http.server.BaseHTTPRequestHandler):
    def _h(self):
        body = self.rfile.read(int(self.headers.get("content-length") or 0))
        i = next(n)
        open(f"/out/req-{i}.json", "w").write(json.dumps({"method": self.command, "path": self.path, "headers": dict(self.headers), "body": body.decode(errors="replace")}, indent=1))
        if self.command == "GET":
            self.send_response(404); self.end_headers(); return
        req = json.loads(body)
        names = [t.get("name") for t in req.get("tools") or []]
        if names == ["permission_decision"]:
            import os
            parts = [{"type": "stream-start", "warnings": []}, {"type": "tool-call", "toolCallId": f"r{i}", "toolName": "permission_decision", "input": json.dumps({"decision": os.environ.get("REVIEW", "caution"), "rationale": "probe"})}, finish("tool-calls")]
        elif not req.get("tools"):
            parts = [{"type": "stream-start", "warnings": []}, {"type": "text-start", "id": "t"}, {"type": "text-delta", "id": "t", "delta": "probe"}, {"type": "text-end", "id": "t"}, finish("stop")]
        else:
            state["main"] += 1
            if state["main"] == 1:
                parts = [{"type": "stream-start", "warnings": []},
                         {"type": "tool-call", "toolCallId": "c1", "toolName": "read_file", "input": json.dumps({"path": "a.txt"})},
                         {"type": "tool-call", "toolCallId": "c2", "toolName": "shell", "input": json.dumps({"request": {"action": "run", "command": "cat a.txt"}})},
                         finish("tool-calls")]
            else:
                parts = [{"type": "stream-start", "warnings": []}, {"type": "text-start", "id": "t"}, {"type": "text-delta", "id": "t", "delta": "done"}, {"type": "text-end", "id": "t"}, finish("stop")]
        self.send_response(200); self.send_header("content-type", "text/event-stream"); self.end_headers()
        self.wfile.write(sse(parts))
    do_GET = do_POST = _h
    def log_message(self, *a): pass
http.server.ThreadingHTTPServer(("127.0.0.1", 8787), H).serve_forever()
