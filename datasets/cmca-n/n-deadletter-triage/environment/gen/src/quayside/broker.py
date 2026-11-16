"""The queue: deliveries, leases, results and the dead-letter queue (docs/queue.md).

An Engine runs from one `started` line to the next `stopping` line. The
caller hands it the messages producers enqueue, configuration reloads and
the passing of time; `env.attempt(message, at)` stands for the handler and
the downstream service it calls. Every decision goes to `log` as
(time, stream, text) and every final one to `outcomes`.
"""

import heapq

from . import checkpoint, dedupe, lease, retry, schema

# At the same millisecond, results come first, then lease expiries, then deliveries.
FINISH, EXPIRE, READY = 0, 1, 2


class Engine:
    def __init__(self, cfg, env, state=None, at: int = 0):
        self.cfg = cfg
        self.env = env
        self.messages: dict[str, dict] = {}
        self.keys = dedupe.KeyStore()
        self.heap: list = []
        self.seq = 0
        self.log: list[tuple[int, str, str]] = []
        self.outcomes: dict[str, tuple[str, int, int]] = {}
        # message id -> (epoch, started, visibility, heartbeat interval) of the delivery holding its lease
        self.current: dict[str, tuple[int, int, int, int]] = {}
        if state is not None:
            checkpoint.restore(self, state)
        for m in sorted(self.messages.values(), key=lambda m: (m["ready_at"], m["id"])):
            self._push(max(m["ready_at"], at), READY, m["id"], m["epoch"])

    def _push(self, at: int, kind: int, mid: str, data) -> None:
        self.seq += 1
        heapq.heappush(self.heap, (at, kind, self.seq, mid, data))

    def reload(self, cfg) -> None:
        """A new configuration; deliveries already running keep their lease."""
        self.cfg = cfg

    def enqueue(self, mid: str, job_type: str, payload, at: int) -> None:
        self.messages[mid] = {
            "id": mid, "type": job_type, "payload": payload, "enqueued_at": at, "ready_at": at,
            "receives": 0, "failures": 0, "lost": 0, "epoch": 0, "claimed": False,
        }
        self._push(at, READY, mid, 0)

    def advance(self, until: int) -> None:
        """Runs everything due before until."""
        while self.heap and self.heap[0][0] < until:
            at, kind, _, mid, data = heapq.heappop(self.heap)
            if kind == READY:
                self._deliver(at, mid, data)
            elif kind == EXPIRE:
                self._expire(at, mid, data)
            else:
                self._finish(at, mid, data)

    def stop(self, at: int) -> dict:
        """Abandons running deliveries and returns the checkpoint."""
        for mid, (_, started, visibility, interval) in sorted(self.current.items()):
            m = self.messages[mid]
            m["ready_at"] = lease.lease_end(started, at, visibility, interval, self.cfg.heartbeat)
            m["epoch"] += 1
            self.log.append((at, "worker", f"{mid} receive={m['receives']} abandoned"))
        self.current.clear()
        self.heap.clear()
        return checkpoint.dump(self, at)

    def pending(self) -> int:
        return len(self.messages)

    def _close(self, at: int, m: dict, disposition: str, line: str) -> None:
        self.outcomes[m["id"]] = (disposition, at, m["receives"])
        self.log.append((at, "queue", line))
        del self.messages[m["id"]]
        self.current.pop(m["id"], None)

    def _dead(self, at: int, m: dict, reason: str) -> None:
        if m["claimed"]:
            self.keys.release(dedupe.key_of(m["type"], m["payload"]), m["id"])
        self._close(at, m, f"dead-letter:{reason}", f"dead-letter {m['id']} reason={reason}")

    def _deliver(self, at: int, mid: str, epoch: int) -> None:
        m = self.messages.get(mid)
        if m is None or m["epoch"] != epoch:
            return
        m["receives"] += 1
        problem = schema.check(m["type"], m["payload"], self.cfg)
        if problem is not None:
            self.log.append((at, "worker", f"{mid} receive={m['receives']} refused \"{problem}\""))
            self._dead(at, m, "schema-rejected")
            return
        if not m["claimed"]:
            key = dedupe.key_of(m["type"], m["payload"])
            verdict, owner = self.keys.check(key, mid, dedupe.digest(m["payload"]), at)
            if verdict == "duplicate":
                self._close(at, m, "duplicate", f"duplicate {mid} of={owner}")
                return
            if verdict == "conflict":
                self.log.append((at, "worker", f"{mid} receive={m['receives']} refused \"key {key} held by {owner}\""))
                self._dead(at, m, "key-conflict")
                return
            m["claimed"] = True
        job = self.cfg.job(m["type"])
        outcome, ms, retry_after, detail = self.env.attempt(m, at)
        m["epoch"] += 1
        interval = lease.heartbeat_interval(self.cfg, job)
        self.current[mid] = (m["epoch"], at, job.visibility_ms, interval)
        self._push(at + ms, FINISH, mid, (m["epoch"], m["receives"], outcome, ms, retry_after, detail))
        expiry = lease.expires_at(at, ms, job.visibility_ms, interval, self.cfg.heartbeat)
        if expiry is not None:
            self._push(expiry, EXPIRE, mid, m["epoch"])

    def _expire(self, at: int, mid: str, epoch: int) -> None:
        m = self.messages.get(mid)
        if m is None or m["epoch"] != epoch or mid not in self.current:
            return
        del self.current[mid]
        m["lost"] += 1
        self.log.append((at, "worker", f"{mid} receive={m['receives']} lease expired"))
        if m["lost"] >= self.cfg.max_lost:
            self._dead(at, m, "lease-lost")
            return
        m["epoch"] += 1
        m["ready_at"] = at
        self._push(at, READY, mid, m["epoch"])

    def _finish(self, at: int, mid: str, data) -> None:
        epoch, receive, outcome, ms, retry_after, detail = data
        result = f"{mid} receive={receive} {outcome} ms={ms}"
        if outcome == "throttled":
            result += f" retry_after={retry_after}ms"
        if detail:
            result += f" \"{detail}\""
        m = self.messages.get(mid)
        if m is None or m["epoch"] != epoch:
            self.log.append((at, "worker", result + " ack refused (lease lost)"))
            return
        self.log.append((at, "worker", result))
        del self.current[mid]
        verdict = retry.settle(m, outcome, retry_after, self.cfg.job(m["type"]), at)
        if verdict[0] == "done":
            self.keys.complete(dedupe.key_of(m["type"], m["payload"]), mid, at + self.cfg.window_ms)
            self._close(at, m, "done", f"done {mid}")
        elif verdict[0] == "dead":
            self._dead(at, m, verdict[1])
        else:
            m["epoch"] += 1
            m["ready_at"] = verdict[1]
            self._push(verdict[1], READY, mid, m["epoch"])
