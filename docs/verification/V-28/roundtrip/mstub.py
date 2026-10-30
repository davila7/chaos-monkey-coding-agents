"""Scripted, streaming stand-in for the Messages API (V-28 round trip; no model cost).

Each POST gets the next step of /work/mscript.json (a list of content-block
lists) and is appended to /out/mrequests.jsonl.
"""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SCRIPT = json.load(open("/work/mscript.json"))
step = {"i": 0}


def ev(t: str, d: dict) -> bytes:
    return f"event: {t}\ndata: {json.dumps(dict(type=t, **d))}\n\n".encode()


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["content-length"])))
        with open("/out/mrequests.jsonl", "a") as f:
            f.write(json.dumps({"path": self.path, "headers": {k.lower(): v for k, v in self.headers.items() if k.lower() in ("anthropic-version", "x-api-key")}, "body": body}) + "\n")
        i = min(step["i"], len(SCRIPT) - 1)
        step["i"] += 1
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.end_headers()
        w = self.wfile.write
        usage = {"input_tokens": 10, "cache_read_input_tokens": 100 * i, "cache_creation_input_tokens": 50, "output_tokens": 1}
        w(ev("message_start", {"message": {"id": f"msg_{i}", "type": "message", "role": "assistant", "model": body["model"], "content": [], "stop_reason": None, "stop_sequence": None, "usage": usage}}))
        stop = "end_turn"
        for k, b in enumerate(SCRIPT[i]):
            if b["type"] == "tool_use":
                stop = "tool_use"
                w(ev("content_block_start", {"index": k, "content_block": {"type": "tool_use", "id": b["id"], "name": b["name"], "input": {}}}))
                w(ev("content_block_delta", {"index": k, "delta": {"type": "input_json_delta", "partial_json": json.dumps(b["input"])}}))
            elif b["type"] == "thinking":
                w(ev("content_block_start", {"index": k, "content_block": {"type": "thinking", "thinking": "", "signature": ""}}))
                w(ev("content_block_delta", {"index": k, "delta": {"type": "thinking_delta", "thinking": b["thinking"]}}))
                w(ev("content_block_delta", {"index": k, "delta": {"type": "signature_delta", "signature": b["signature"]}}))
            else:
                w(ev("content_block_start", {"index": k, "content_block": {"type": "text", "text": ""}}))
                w(ev("content_block_delta", {"index": k, "delta": {"type": "text_delta", "text": b["text"]}}))
            w(ev("content_block_stop", {"index": k}))
        w(ev("message_delta", {"delta": {"stop_reason": stop, "stop_sequence": None}, "usage": {"output_tokens": 20}}))
        w(ev("message_stop", {}))

    def log_message(self, *args):
        pass


ThreadingHTTPServer(("127.0.0.1", 8788), Handler).serve_forever()
