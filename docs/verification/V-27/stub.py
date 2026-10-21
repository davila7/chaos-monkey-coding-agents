"""Stub model for fx and fxh in the AI Gateway stream format (V-22 method, no model cost).

Each main-model request gets the next scripted step: a tool call, or a final
text once the script is done. The script comes from SCRIPT (a JSON list of
[tool name, arguments] steps) or, with SCRIPT unset, from the conformance
probe whose instruction appears in the request. Every request is saved under
OUT as req-<n>.json.

    OUT=<dir> [PORT=8787] [HOST=127.0.0.1] [SCRIPT='[["read_file", {"path": "a.txt"}]]'] python3 stub.py
"""

import http.server
import itertools
import json
import os
import threading

OUT = os.environ["OUT"]
PORT = int(os.environ.get("PORT", "8787"))
HOST = os.environ.get("HOST", "127.0.0.1")
SCRIPT = json.loads(os.environ["SCRIPT"]) if os.environ.get("SCRIPT") else None

# One script per conformance probe (cmca_harbor.probes), keyed by a phrase of its instruction.
PROBES = {
    "file reading tool": [["read_file", {"path": "/app/probe/notes.txt"}]],
    "file writing tool": [["write_file", {"path": "/app/probe/answer.txt", "content": "ready"}]],
    "file editing tool": [
        ["read_file", {"path": "/app/probe/config.txt"}],
        ["edit_file", {"path": "/app/probe/config.txt", "old_string": "mode=off", "new_string": "mode=on"}],
    ],
    "file search tool": [["grep_files", {"pattern": "marigold", "path": "/app/probe/docs"}]],
    "Run this exact shell command": [["shell", {"action": "run", "command": "cat /app/probe/notes.txt; touch /app/probe/shell.done"}]],
}

USAGE = {"inputTokens": {"total": 10, "noCache": 10, "cacheRead": 0, "cacheWrite": 0}, "outputTokens": {"total": 5, "text": 5, "reasoning": 0}}
counter = itertools.count()
lock = threading.Lock()


def sse(parts):
    return "".join(f"data: {json.dumps(p)}\n\n" for p in parts).encode()


def finish(reason):
    return {"type": "finish", "finishReason": {"unified": reason, "raw": reason}, "usage": USAGE}


def text(t):
    return [{"type": "stream-start", "warnings": []}, {"type": "text-start", "id": "t"}, {"type": "text-delta", "id": "t", "delta": t}, {"type": "text-end", "id": "t"}, finish("stop")]


def script_for(body: str):
    if SCRIPT is not None:
        return SCRIPT
    for phrase, script in PROBES.items():
        if phrase in body:
            return script
    return []


class Handler(http.server.BaseHTTPRequestHandler):
    def _handle(self):
        raw = self.rfile.read(int(self.headers.get("content-length") or 0))
        with lock:
            n = next(counter)
        with open(os.path.join(OUT, f"req-{n}.json"), "w") as f:
            json.dump({"method": self.command, "path": self.path, "headers": dict(self.headers), "body": raw.decode(errors="replace")}, f, indent=1)
        if self.command != "POST":
            self.send_response(404)
            self.end_headers()
            return
        req = json.loads(raw)
        tools = [t.get("name") for t in req.get("tools") or []]
        if not tools:
            parts = text("probe")
        else:
            # The user turn only: fx's system prompt could contain a probe phrase.
            body = json.dumps([m for m in req.get("prompt") or [] if m.get("role") == "user"])
            done = sum(1 for m in req.get("prompt") or [] if m.get("role") == "tool")
            script = script_for(body)
            if done < len(script):
                name, args = script[done]
                parts = [{"type": "stream-start", "warnings": []}, {"type": "tool-call", "toolCallId": f"call-{done + 1}", "toolName": name, "input": json.dumps(args)}, finish("tool-calls")]
            else:
                parts = text("done")
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.end_headers()
        self.wfile.write(sse(parts))

    do_GET = do_POST = _handle

    def log_message(self, *args):
        pass


http.server.ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
