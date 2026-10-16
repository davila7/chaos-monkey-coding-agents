"""summary.json (docs/output.md, section 3)."""

import json
from collections import Counter


class Summary:
    def __init__(self):
        self.requests = 0
        self.status = Counter()
        self.routes = Counter()

    def add(self, ctx, status: int) -> None:
        self.requests += 1
        self.status[str(status)] += 1
        self.routes[ctx.route.name if ctx.route is not None else "(none)"] += 1

    def text(self, extra: dict) -> str:
        d = {"requests": self.requests, "status": dict(self.status), "routes": dict(self.routes)}
        for k, v in extra.items():
            d[k] = v
        return json.dumps(d, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
