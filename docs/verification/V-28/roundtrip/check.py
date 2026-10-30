"""Checks the Messages API requests of the V-28 round trip and prints what they carry."""

import json
import sys
from pathlib import Path

out = Path(sys.argv[1])
reqs = [json.loads(x) for x in (out / "mrequests.jsonl").read_text().splitlines()]
print("requests", len(reqs), "paths", sorted({r["path"] for r in reqs}))
first = reqs[0]["body"]
print("model", first["model"], "max_tokens", first["max_tokens"])
print("thinking", json.dumps(first.get("thinking")), "output_config", json.dumps(first.get("output_config")), "cache_control", json.dumps(first.get("cache_control")))
print("system blocks", len(first["system"]), "starts", json.dumps(first["system"][0]["text"][:60]))
print("tools", [(t["name"], sorted(t["input_schema"].get("properties", {}))) for t in first["tools"]])
for a, b in zip(reqs, reqs[1:]):
    ma, mb = a["body"]["messages"], b["body"]["messages"]
    same = {k: a["body"][k] == b["body"][k] for k in ("system", "tools")}
    print("next request: system and tools unchanged", same, "| earlier messages kept as sent", mb[: len(ma) - 1] == ma[:-1], "| last earlier message is a prefix", json.dumps(ma[-1])[:-2] in json.dumps(mb[len(ma) - 1]))
last = reqs[-1]["body"]["messages"]
for m in last:
    for c in m["content"] if isinstance(m["content"], list) else []:
        if c["type"] == "thinking":
            print("thinking block passed back", json.dumps({k: c[k] for k in ("thinking", "signature")}))
        elif c["type"] == "tool_use":
            print("tool_use", c["id"], c["name"], json.dumps(c["input"])[:80])
        elif c["type"] == "tool_result":
            print("tool_result", c["tool_use_id"], json.dumps(c["content"])[:160])
print("usage log")
print((out / "usage.jsonl").read_text().strip())
print("a.txt", json.dumps((out / "a.txt").read_text()))
