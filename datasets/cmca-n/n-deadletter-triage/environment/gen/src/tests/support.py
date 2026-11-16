from quayside import config

TEXT = """
rev = 7
accept_schema = [2, 3]

[retry]
max_attempts = 4
backoff = "1m"
backoff_max = "15m"

[lease]
visibility = "10m"
heartbeat = true
max_lost = 3

[dedupe]
window = "24h"

[jobs."refund.issue"]
max_attempts = 6
backoff = "2m"
"""

MINUTE = 60_000
T0 = 1_800_000_000_000


def cfg(text: str = TEXT):
    return config.parse(text)


def at(minutes: float) -> int:
    """Milliseconds from an arbitrary origin."""
    return T0 + int(minutes * MINUTE)


class Env:
    """A handler whose results come from a script: {message id: [(outcome, ms, retry_after_ms), ...]}."""

    def __init__(self, script: dict, default=("ok", 1000, 0)):
        self.script = {k: list(v) for k, v in script.items()}
        self.default = default
        self.calls: list[tuple[str, int]] = []

    def attempt(self, m: dict, when: int):
        self.calls.append((m["id"], when))
        queue = self.script.get(m["id"])
        outcome, ms, retry_after = queue.pop(0) if queue else self.default
        return (outcome, ms, retry_after, "")


def email(order: str = "o1", **extra) -> dict:
    return {"v": 2, "idem_key": f"em-{order}-confirm", "order": order, "template": "confirm", "to": "c1", "sent_at": "2027-01-01T00:00:00.000Z", **extra}


def refund(order: str = "o1", part: int = 1, amount: int = 1000, **extra) -> dict:
    return {"v": 3, "idem": f"rf-{order}-{part}", "order": order, "amount": amount, "card": "ok", "sent_at": "2027-01-01T00:00:00.000Z", **extra}
