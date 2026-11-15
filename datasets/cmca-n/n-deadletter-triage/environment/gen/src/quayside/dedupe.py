"""Idempotency keys (docs/queue.md 5)."""

import hashlib
import json

IGNORED = ("sent_at",)


def key_of(job_type: str, payload: dict) -> str:
    field = "idem" if payload["v"] >= 3 else "idem_key"
    idem = payload.get(field)
    if idem:
        return f"{job_type}:{idem}"
    return f"{job_type}:order:{payload['order']}"


def digest(payload: dict) -> str:
    body = {k: v for k, v in payload.items() if k not in IGNORED}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]


class KeyStore:
    """key -> [owner message id, payload digest, held until (None while the owner is not done)]."""

    def __init__(self):
        self.entries: dict[str, list] = {}

    def check(self, key: str, owner: str, dig: str, now: int) -> tuple[str, str | None]:
        """("run", None), ("duplicate", owner) or ("conflict", owner); "run" claims a free key."""
        e = self.entries.get(key)
        if e is not None and e[2] is not None and e[2] <= now:
            del self.entries[key]
            e = None
        if e is None:
            self.entries[key] = [owner, dig, None]
            return ("run", None)
        if e[0] == owner:
            return ("run", None)
        if e[1] == dig:
            return ("duplicate", e[0])
        return ("conflict", e[0])

    def complete(self, key: str, owner: str, until: int) -> None:
        e = self.entries.get(key)
        if e is not None and e[0] == owner:
            e[2] = until

    def release(self, key: str, owner: str) -> None:
        e = self.entries.get(key)
        if e is not None and e[0] == owner:
            del self.entries[key]
