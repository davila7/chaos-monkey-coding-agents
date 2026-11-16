"""Traffic, downstream states and service events of a quayside history, drawn
from a seeded generator that does not depend on the Python version
(splitmix64 on ints).

draw(spec) returns the enqueued messages, the downstream state changes and
the service events of one spec; build.py runs them through the packages and
writes the logs.
"""

from datetime import datetime, timedelta, timezone

MASK = (1 << 64) - 1
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
MINUTE = 60_000


class Draw:
    def __init__(self, seed: int):
        self.state = seed & MASK

    def next(self) -> int:
        self.state = (self.state + 0x9E3779B97F4A7C15) & MASK
        z = self.state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK
        return z ^ (z >> 31)

    def below(self, n: int) -> int:
        return self.next() % n

    def chance(self, frac) -> bool:
        return self.below(frac[1]) < frac[0]

    def weighted(self, pairs):
        total = sum(w for _, w in pairs)
        r = self.below(total)
        for item, w in pairs:
            if r < w:
                return item
            r -= w
        raise AssertionError("unreachable")


def to_ms(text: str) -> int:
    return (datetime.fromisoformat(text) - EPOCH) // timedelta(milliseconds=1)


def stamp(ms: int) -> str:
    t = EPOCH + timedelta(milliseconds=ms)
    return t.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ms % 1000:03d}Z"


PUBLIC = {
    "seed": 60917,
    "first_id": 1,
    "start": "2027-06-08T00:00:00+00:00",
    "end": "2027-06-09T18:00:00+00:00",
    "day": (7, 22),
    "rate_day": 3,
    "rate_night": 1,
    "lines": [(1, 30), (2, 20), (3, 12), (5, 10), (8, 8), (12, 6), (16, 5), (20, 4), (28, 3), (36, 2)],
    "skus": 400,
    "versions": {"email.send": [(2, 1)], "refund.issue": [(3, 1)], "invoice.render": [(3, 1)], "stock.sync": [(3, 1)]},
    "stale_idem": (0, 100),
    "refund": (7, 100),
    "refund_delay_min": (15, 300),
    "partial": {"from": "2027-06-08T18:00:00+00:00", "chance": (45, 100), "parts": 3},
    "expired": (3, 100),
    "resend": (2, 100),
    "edit": (2, 100),
    "channel": {"from": "2027-06-08T22:00:00+00:00", "chance": (15, 100), "name": "channel", "value": "app"},
    "extra_fields": [],
    "campaign": {"from": "2027-06-09T07:00:00+00:00", "to": "2027-06-09T08:30:00+00:00", "rate": 16, "id": "0609"},
    "poison": [
        {"from": "2027-06-09T02:10:00+00:00", "to": "2027-06-09T02:35:00+00:00", "rate": 1, "kind": "missing"},
    ],
    "downstream": [
        ("2027-06-08T12:05:00+00:00", "payments", "down", 0),
        ("2027-06-08T12:40:00+00:00", "payments", "ok", 0),
        ("2027-06-08T17:10:00+00:00", "mailer", "throttled", 30),
        ("2027-06-08T17:16:00+00:00", "mailer", "ok", 0),
        ("2027-06-09T07:05:00+00:00", "mailer", "throttled", 30),
        ("2027-06-09T07:15:00+00:00", "mailer", "ok", 0),
        ("2027-06-09T07:31:00+00:00", "mailer", "throttled", 30),
        ("2027-06-09T07:43:00+00:00", "mailer", "ok", 0),
        ("2027-06-09T08:02:00+00:00", "mailer", "throttled", 30),
        ("2027-06-09T08:10:00+00:00", "mailer", "ok", 0),
        ("2027-06-09T13:00:00+00:00", "inventory", "down", 0),
        ("2027-06-09T14:20:00+00:00", "inventory", "ok", 0),
    ],
    "events": [
        ("2027-06-08T00:00:00+00:00", "started config=r041"),
        ("2027-06-08T09:00:00+00:00", "config reload rev=42"),
        ("2027-06-08T11:00:00+00:00", "stopping"),
        ("2027-06-08T11:00:05+00:00", "started config=r042"),
        ("2027-06-08T14:00:00+00:00", "stopping"),
        ("2027-06-08T14:00:05+00:00", "started config=r042"),
        ("2027-06-08T20:00:00+00:00", "config reload rev=43"),
        ("2027-06-09T05:00:00+00:00", "stopping"),
        ("2027-06-09T05:00:04+00:00", "started config=r043"),
    ],
}

PRODUCERS = {"email.send": "notifier", "refund.issue": "billing", "invoice.render": "storefront", "stock.sync": "storefront"}
PREFIX = {"email.send": "em", "refund.issue": "rf", "invoice.render": "inv", "stock.sync": "st"}


def stops(spec: dict) -> list[tuple[int, int]]:
    out, down = [], None
    for at, line in spec["events"]:
        if line == "stopping":
            down = to_ms(at)
        elif line.startswith("started") and down is not None:
            out.append((down, to_ms(at)))
            down = None
    return out


def draw(spec: dict) -> dict:
    d = Draw(spec["seed"])
    start, end = to_ms(spec["start"]), to_ms(spec["end"])
    windows = stops(spec)
    raw: list[tuple] = []

    def add(at: int, job: str, producer: str, payload: dict) -> None:
        payload = dict(payload)
        payload["sent_at"] = stamp(max(start, at - d.below(400)))
        raw.append((at, len(raw), job, producer, payload))

    def idem_fields(job: str, order: str, suffix: str) -> dict:
        v = d.weighted(spec["versions"][job])
        own, other = ("idem", "idem_key") if v >= 3 else ("idem_key", "idem")
        fields = {"v": v, own: f"{PREFIX[job]}-{order}-{suffix}"}
        if d.chance(spec["stale_idem"]):
            fields[other] = f"{PREFIX[job]}-{order}"
        return fields

    def extras(job: str, at: int, order_extra: dict) -> dict:
        out = dict(order_extra)
        for x in spec["extra_fields"]:
            if job in x["types"] and at >= to_ms(x["from"]) and d.chance(x["chance"]):
                out[x["name"]] = x["values"][d.below(len(x["values"]))]
        return out

    order_no = 0
    partial_from = to_ms(spec["partial"]["from"])
    channel = spec["channel"]
    for minute in range(start, end, MINUTE):
        hour = (minute // 3_600_000) % 24
        rate = spec["rate_day"] if spec["day"][0] <= hour < spec["day"][1] else spec["rate_night"]
        for _ in range(d.below(2 * rate + 1)):
            t = minute + d.below(MINUTE)
            order_no += 1
            order = f"o{100000 + order_no}"
            cust = f"c{10000 + d.below(90000)}"
            ox = {}
            if channel and t >= to_ms(channel["from"]) and d.chance(channel["chance"]):
                ox[channel["name"]] = channel["value"]
            te = t + d.below(2000)
            add(te, "email.send", "notifier", {**idem_fields("email.send", order, "confirm"), "order": order, "template": "confirm", "to": cust, **extras("email.send", te, ox)})
            lines = [f"sku-{d.below(spec['skus']):04d}" for _ in range(d.weighted(spec["lines"]))]
            ti = t + 500 + d.below(4000)
            add(ti, "invoice.render", "storefront", {**idem_fields("invoice.render", order, "1"), "order": order, "lines": lines, **extras("invoice.render", ti, ox)})
            ts = t + d.below(3000)
            add(ts, "stock.sync", "storefront", {**idem_fields("stock.sync", order, "1"), "order": order, "sku": lines[0], "qty": len(lines), **extras("stock.sync", ts, ox)})
            if d.chance(spec["refund"]):
                lo, hi = spec["refund_delay_min"]
                tr = t + (lo + d.below(hi - lo)) * MINUTE + d.below(MINUTE)
                parts = 1
                if tr >= partial_from and d.chance(spec["partial"]["chance"]):
                    parts = 2 + d.below(spec["partial"]["parts"] - 1)
                card = "expired" if d.chance(spec["expired"]) else "ok"
                for k in range(parts):
                    amount = 500 + d.below(20000)
                    trk = tr + k * (1000 + d.below(20000))
                    add(trk, "refund.issue", "billing", {**idem_fields("refund.issue", order, str(k + 1)), "order": order, "amount": amount, "card": card, **extras("refund.issue", trk, ox)})
    campaign = spec.get("campaign")
    if campaign:
        for minute in range(to_ms(campaign["from"]), to_ms(campaign["to"]), MINUTE):
            for _ in range(d.below(2 * campaign["rate"] + 1)):
                t = minute + d.below(MINUTE)
                cust = f"c{10000 + d.below(90000)}"
                add(t, "email.send", "campaigns", {"v": 2, "idem_key": f"nl-{campaign['id']}-{cust}", "order": "-", "template": "newsletter", "to": cust, **extras("email.send", t, {})})
    for p in spec["poison"]:
        n = 0
        for minute in range(to_ms(p["from"]), to_ms(p["to"]), MINUTE):
            for _ in range(d.below(2 * p["rate"] + 1)):
                n += 1
                t = minute + d.below(MINUTE)
                order = f"o{100000 + 1 + d.below(order_no)}"
                if p["kind"] == "missing":
                    payload = {"v": 3, "idem": f"pos-{order}-{n}", "order": order, "total": f"{5 + d.below(200)}.{d.below(100):02d}", "card": "ok"}
                else:
                    payload = {"v": 1, "idem": f"pos-{order}-{n}", "order": order, "amount": 500 + d.below(20000), "card": "ok"}
                add(t, "refund.issue", "pos", payload)
    base = list(raw)
    for at, _, job, producer, payload in base:
        if producer == "pos":
            continue
        if d.chance(spec["resend"]):
            add(at + 5000 + d.below(85000), job, producer, {k: v for k, v in payload.items() if k != "sent_at"})
        if job == "refund.issue" and d.chance(spec["edit"]):
            edited = {k: v for k, v in payload.items() if k != "sent_at"}
            edited["amount"] = payload["amount"] + 1 + d.below(500)
            add(at + (10 + d.below(30)) * MINUTE, job, "support", edited)
    kept = sorted((r for r in raw if start <= r[0] < end and not any(a <= r[0] <= b for a, b in windows)), key=lambda r: (r[0], r[1]))
    messages = [(at, f"m{spec['first_id'] + i:07d}", job, producer, payload) for i, (at, _, job, producer, payload) in enumerate(kept)]
    services = sorted({s for _, s, _, _ in spec["downstream"]} | {"mailer", "payments", "pdfgen", "inventory"})
    downstream = [(start, s, "ok", 0) for s in services] + [(to_ms(at), s, st, ra * 1000) for at, s, st, ra in spec["downstream"]]
    events = [(to_ms(at), line) for at, line in spec["events"]]
    return {"messages": messages, "downstream": downstream, "events": events}
