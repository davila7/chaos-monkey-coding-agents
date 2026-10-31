"""Scratch: hash-first join, patched into cmca_analysis for impact measurement (not committed)."""
import hashlib, json, re
from cmca_analysis import ingest, trials

def _canon(cap, args):
    if cap == "shell":
        cmd = args.get("command", args.get("cmd"))
        return re.sub(r"\s+", " ", cmd.strip()) if isinstance(cmd, str) else None
    if cap and cap.startswith("mcp."):
        return json.dumps(args, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return None

def _h(s): return hashlib.sha256(s.encode()).hexdigest()[:16]

def pair(events, calls, name_of, args_of):
    by = {}
    for c in calls: by.setdefault(name_of(c), []).append(c)
    used = set(); out = []
    for e in sorted(events, key=lambda r: r.get("seq") if r.get("seq") is not None else -1):
        same = [c for c in by.get(e.get("tool_name") or "", []) if id(c) not in used]
        pick = None
        if e.get("args_hash"):
            for c in same:
                k = _canon(e.get("capability"), args_of(c))
                if k is not None and _h(k) == e["args_hash"]: pick = c; break
        if pick is None and same: pick = same[0]
        if pick is not None: used.add(id(pick))
        out.append((e, pick))
    return out

def ingest_join(events, calls):
    cs = [c for c in calls if not ingest.unlogged(c.name, c.args, c.observation)]
    return pair(events, cs, lambda c: ingest.LOG_NAMES.get(c.name, c.name), lambda c: c.args)

def trials_join(events, calls):
    cs = [c for c in calls if not ingest.unlogged(c[0], c[2] if len(c) > 2 else {}, c[1])]
    def nm(c):
        n = ingest.MCP_PREFIX.sub("", c[0]); return ingest.LOG_NAMES.get(n, n)
    return pair(events, cs, nm, lambda c: c[2] if len(c) > 2 else {})

def patch():
    ingest.join = ingest_join
    trials._join = trials_join
    import cmca_analysis
    for m in list(__import__('sys').modules.values()):
        if getattr(m, '__name__', '').startswith('cmca_analysis') and getattr(m, 'join', None) is not None and m is not ingest:
            if getattr(m, 'join') is not ingest_join and getattr(m.join, '__module__', '') == 'cmca_analysis.ingest': m.join = ingest_join

def patch_frame():
    import re as _re
    from cmca_analysis import reconcile
    reconcile._CODEX_FRAME = _re.compile(r"^(?:(?:Chunk ID|Wall time|Process exited with code|Process running with session ID|Original token count|Exit code):? [^\n]*\n)+Output:(?:\n|$)")
