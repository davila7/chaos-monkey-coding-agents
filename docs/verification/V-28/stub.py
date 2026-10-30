"""Stub Messages API model for codex-claude conformance (V-28 method, no model cost).

The bridge in the agent container calls this stub in place of the Anthropic
API. Each request gets the next step of the conformance probe whose
instruction appears in a user text block: a tool call, or a final text once
the probe's calls are done. Every request is saved under OUT as req-<n>.json.

    OUT=<dir> [PORT=8788] [HOST=0.0.0.0] python3 stub.py
"""

import http.server
import itertools
import json
import os
import re
import threading

OUT = os.environ["OUT"]
PORT = int(os.environ.get("PORT", "8788"))
HOST = os.environ.get("HOST", "0.0.0.0")

def patch(op: str, path: str, body: str) -> dict:
    return {"input": f"*** Begin Patch\n*** {op} File: {path}\n{body}*** End Patch\n"}

# One script per conformance probe (cmca_harbor.probes), keyed by a phrase of its instruction.
PROBES = {
    "file writing tool": [["apply_patch", patch("Add", "/app/probe/answer.txt", "+ready\n")]],
    "file editing tool": [["apply_patch", patch("Update", "/app/probe/config.txt", "@@\n-mode=off\n+mode=on\n")]],
}
SHELL = re.compile(r"Run this exact shell command once: `([^`]+)`")

counter = itertools.count()
lock = threading.Lock()


def ev(t: str, d: dict) -> bytes:
    return f"event: {t}\ndata: {json.dumps(dict(type=t, **d))}\n\n".encode()


def user_text(messages: list) -> str:
    out = []
    for m in messages:
        if m.get("role") != "user":
            continue
        content = m["content"] if isinstance(m["content"], list) else [{"type": "text", "text": m["content"]}]
        out += [b.get("text", "") for b in content if b.get("type") == "text"]
    return "\n".join(out)


def script_for(text: str) -> list:
    m = SHELL.search(text)
    if m:
        return [["exec_command", {"cmd": m.group(1)}]]
    for phrase, script in PROBES.items():
        if phrase in text:
            return script
    return []


class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("content-length") or 0))
        with lock:
            n = next(counter)
        with open(os.path.join(OUT, f"req-{n}.json"), "w") as f:
            json.dump({"path": self.path, "body": json.loads(raw)}, f, indent=1)
        req = json.loads(raw)
        messages = req.get("messages") or []
        done = sum(1 for m in messages if isinstance(m.get("content"), list) for b in m["content"] if b.get("type") == "tool_result")
        script = script_for(user_text(messages))
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.end_headers()
        w = self.wfile.write
        usage = {"input_tokens": 10, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0, "output_tokens": 1}
        w(ev("message_start", {"message": {"id": f"msg_{n}", "type": "message", "role": "assistant", "model": req["model"], "content": [], "stop_reason": None, "stop_sequence": None, "usage": usage}}))
        if done < len(script):
            name, args = script[done]
            w(ev("content_block_start", {"index": 0, "content_block": {"type": "tool_use", "id": f"toolu_{n}", "name": name, "input": {}}}))
            w(ev("content_block_delta", {"index": 0, "delta": {"type": "input_json_delta", "partial_json": json.dumps(args)}}))
            stop = "tool_use"
        else:
            w(ev("content_block_start", {"index": 0, "content_block": {"type": "text", "text": ""}}))
            w(ev("content_block_delta", {"index": 0, "delta": {"type": "text_delta", "text": "done"}}))
            stop = "end_turn"
        w(ev("content_block_stop", {"index": 0}))
        w(ev("message_delta", {"delta": {"stop_reason": stop, "stop_sequence": None}, "usage": {"output_tokens": 5}}))
        w(ev("message_stop", {}))

    def do_GET(self):
        self.send_response(404)
        self.end_headers()

    def log_message(self, *args):
        pass


http.server.ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
