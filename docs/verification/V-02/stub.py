"""Scripted Responses API stand-in for Codex (V-02, V-03; no model cost).

Each POST to /v1/responses gets the next step of SCRIPT (a JSON list of
lists of output items) and is appended to LOG. `{session_id}` in a step's
arguments becomes the last `Process running with session ID` in the request.

    LOG=<file> SCRIPT=<file> [PORT=8787] python3 stub.py
"""

import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LOG = os.environ["LOG"]
SCRIPT = json.load(open(os.environ["SCRIPT"]))
PORT = int(os.environ.get("PORT", "8787"))
step = {"i": 0}


def sse(ev: dict) -> bytes:
    return f"event: {ev['type']}\ndata: {json.dumps(ev)}\n\n".encode()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"models":[]}')

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("content-length", 0))) or b"{}")
        with open(LOG, "a") as f:
            f.write(json.dumps({"path": self.path, "body": body}) + "\n")
        i = min(step["i"], len(SCRIPT) - 1)
        step["i"] += 1
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.end_headers()
        rid = f"resp_{i}"
        self.wfile.write(sse({"type": "response.created", "response": {"id": rid}}))
        running = re.findall(r"Process running with session ID (\d+)", json.dumps(body))
        for item in SCRIPT[i]:
            if running and "arguments" in item:
                item = {**item, "arguments": item["arguments"].replace("{session_id}", running[-1])}
            self.wfile.write(sse({"type": "response.output_item.done", "item": item}))
        usage = {"input_tokens": 10, "input_tokens_details": {"cached_tokens": 0}, "output_tokens": 5, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 15}
        self.wfile.write(sse({"type": "response.completed", "response": {"id": rid, "usage": usage}}))

    def log_message(self, *args):
        pass


ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
