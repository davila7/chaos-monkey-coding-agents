"""Traffic and service events of a shelfmark history, drawn from a seeded
generator that does not depend on the Python version (splitmix64 on ints).

draw(spec) returns the requests and the service events of one spec; build.py
runs them through the packages and writes the logs.
"""

from datetime import datetime, timedelta, timezone
from math import isqrt
from urllib.parse import quote_plus

MASK = (1 << 64) - 1
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


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

    def pick(self, seq):
        return seq[self.below(len(seq))]

    def chance(self, num: int, den: int) -> bool:
        return self.below(den) < num

    def weighted(self, pairs):
        total = sum(w for _, w in pairs)
        r = self.below(total)
        for item, w in pairs:
            if r < w:
                return item
            r -= w
        raise AssertionError("unreachable")

    def sample(self, population: list, k: int) -> list:
        pool = list(population)
        out = []
        for _ in range(k):
            out.append(pool.pop(self.below(len(pool))))
        return out


def to_ms(text: str) -> int:
    return (datetime.fromisoformat(text) - EPOCH) // timedelta(milliseconds=1)


def stamp(ms: int) -> str:
    t = EPOCH + timedelta(milliseconds=ms)
    return t.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ms % 1000:03d}Z"


WORDS = [
    "river", "winter", "garden", "glass", "harbor", "orchard", "lantern", "salt", "copper", "willow",
    "night", "atlas", "comet", "ember", "falcon", "granite", "island", "juniper", "kettle", "meadow",
    "north", "ocean", "pepper", "quarry", "raven", "silver", "thistle", "violet", "wander", "yarrow",
    "letters", "kingdom", "memory", "station", "stranger", "summer", "tide", "valley", "voyage", "witness",
]
SLOTS = ["slot-1", "slot-2", "slot-3", "slot-4", "slot-5", "slot-6"]


def zipf(items: list, scale: int = 1000) -> list:
    """Weights close to rank ** -1.5, in integers."""
    return [(item, scale // ((rank + 1) * isqrt(rank + 1)) + 1) for rank, item in enumerate(items)]


def queries(d: Draw, count: int) -> list[str]:
    seen, out = set(), []
    while len(out) < count:
        q = " ".join(d.pick(WORDS) for _ in range(1 + d.below(3)))
        if q not in seen:
            seen.add(q)
            out.append(q)
    return out


def variant(d: Draw, q: str) -> str:
    kind = d.below(5)
    if kind == 0:
        return q.title()
    if kind == 1:
        return q.upper()
    if kind == 2:
        return q + " "
    if kind == 3:
        return "  ".join(q.split(" "))
    return " " + q


def tracking(d: Draw, spec: dict, at: int, route: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    r = d.below(100)
    if r < 8:
        out.append(("ref", d.pick(["home", "related", "list"])))
    elif r < 13:
        out.append((spec["click_param"], "".join(d.pick("0123456789abcdef") for _ in range(8))))
    elif r < 19:
        out += [("utm_source", "partner"), ("utm_medium", "referral"), ("utm_campaign", "spring")]
    for extra in spec.get("extra_params", []):
        if at >= to_ms(extra["from"]) and route in extra["routes"] and d.chance(*extra["chance"]):
            out.append((extra["name"], d.pick(extra["values"])))
    return out


def draw(spec: dict) -> dict:
    """Requests (sorted, with ids) and service events for one spec."""
    d = Draw(spec["seed"])
    lo, hi, count = spec["book_heads"]
    heads = d.sample(list(range(lo, hi)), count)
    books = heads + d.sample([b for b in range(1, spec["books"] + 1) if b not in heads], spec["popular_books"] - count)
    authors = d.sample(list(range(1, spec["authors"] + 1)), spec["popular_authors"])
    book_w, author_w = zipf(books), zipf(authors)
    qs = zipf(queries(d, spec["queries"]))
    langs = spec["langs"]
    start, end = to_ms(spec["start"]), to_ms(spec["end"])
    stops = [(to_ms(a), to_ms(b)) for a, b in spec["stops"]]
    partner = spec.get("partner")
    campaign = spec.get("campaign")
    if campaign:
        picks = d.sample(books[:60], len(SLOTS))
    raw = []
    minute = start
    while minute < end:
        hour = int(stamp(minute)[11:13])
        rate = spec["rate_day"] if spec["day"][0] <= hour < spec["day"][1] else spec["rate_night"]
        count = d.below(2 * rate + 1)
        in_campaign = campaign and to_ms(campaign["from"]) <= minute < to_ms(campaign["from"]) + campaign["burst_min"] * 60_000
        if in_campaign:
            count += d.below(2 * campaign["burst_rate"] + 1)
        for _ in range(count):
            at = minute + d.below(60_000)
            if at % 1000 == 0:
                at += 1
            if any(a <= at <= b for a, b in stops) or at >= end:
                d.next()
                continue
            raw.append(request(d, spec, at, book_w, author_w, qs, langs, partner, campaign, picks if campaign else None))
        if d.chance(1, spec["purge_every"]):
            at = minute + 1 + d.below(59_998)
            if at % 1000 == 0:
                at += 1
            if not any(a <= at <= b for a, b in stops):
                raw.append({"at": at, "method": "PURGE", "target": f"/books/{d.weighted(book_w)}", "lang": None, "route": "books", "r": d.below(1000)})
        if d.chance(1, spec["author_purge_every"]):
            at = minute + 1 + d.below(59_998)
            if at % 1000 == 0:
                at += 1
            if not any(a <= at <= b for a, b in stops):
                raw.append({"at": at, "method": "PURGE", "target": f"/authors/{d.weighted(author_w)}", "lang": None, "route": "authors", "r": d.below(1000)})
        minute += 60_000
    raw.sort(key=lambda r: r["at"])
    for i, r in enumerate(raw):
        r["id"] = f"r{spec['first_id'] + i:07d}"
    return {"requests": raw, "events": [(to_ms(t), line) for t, line in spec["events"]], "picks": picks if campaign else []}


def request(d: Draw, spec, at, book_w, author_w, qs, langs, partner, campaign, picks) -> dict:
    route = d.weighted([("books", 55), ("search", 30), ("authors", 12), ("health", 3)])
    lang = d.weighted(langs)
    lang = None if lang == "-" else lang
    params: list[tuple[str, str]] = []
    if route == "health":
        return {"at": at, "method": "GET", "target": "/health", "lang": None, "route": "health", "r": d.below(1000)}
    if route in ("books", "search"):
        params = tracking(d, spec, at, route)
    elif d.chance(1, 20):
        params = [("ref", "related")]
    newsletter = None
    if campaign and route in ("books", "search") and at >= to_ms(campaign["from"]) and d.chance(*campaign["chance"]):
        slot = d.below(len(SLOTS))
        newsletter = slot
        params = [("utm_source", "newsletter"), ("utm_medium", "email"), ("utm_campaign", "may-picks"), ("utm_content", SLOTS[slot])]
        if d.chance(1, 3):
            params.append(("utm_term", d.pick(WORDS)))
    elif partner and route == "books" and at >= to_ms(partner["from"]) and d.chance(*partner["chance"]):
        params = [("utm_source", "blog"), ("utm_medium", "referral"), ("utm_content", d.pick(partner["values"]))]
    if route == "books":
        ident = picks[newsletter] if newsletter is not None and d.chance(4, 5) else d.weighted(book_w)
        target = f"/books/{ident}"
    elif route == "authors":
        target = f"/authors/{d.weighted(author_w)}"
    else:
        q = d.weighted(qs)
        if d.chance(12, 100):
            q = variant(d, q)
        own = [("q", q)]
        page = d.weighted([("1", 88), ("2", 9), ("3", 3)])
        sort = d.weighted([(None, 60), ("newest", 25), ("rating", 15)])
        refine = d.weighted([(None, 96), ("author", 2), ("title", 2)])
        app = d.chance(3, 10)
        if app:
            own = ([("sort", sort)] if sort else []) + ([("refine", refine)] if refine else []) + [("page", page), ("q", q)]
        else:
            if page != "1" or d.chance(1, 2):
                own.append(("page", page))
            if sort:
                own.append(("sort", sort))
            if refine:
                own.append(("refine", refine))
        params = (params + own) if d.chance(1, 2) else (own + params)
        target = "/search"
    if params:
        target += "?" + "&".join(f"{quote_plus(n)}={quote_plus(v)}" for n, v in params)
    return {"at": at, "method": "GET", "target": target, "lang": lang, "route": route, "r": d.below(1000)}


LANGS = [
    ("en-US,en;q=0.9", 30), ("en-GB,en;q=0.8", 12), ("en", 8), ("en-CA,en;q=0.7,fr-CA;q=0.3", 3),
    ("es-ES,es;q=0.9", 8), ("es-MX,es;q=0.8,en;q=0.5", 7), ("fr-FR,fr;q=0.9,en;q=0.6", 6), ("fr-CA,fr;q=0.8", 2),
    ("de-DE,de;q=0.9,en;q=0.5", 6), ("de-AT,de;q=0.8", 2), ("pt-BR,pt;q=0.9", 6), ("pt-PT,pt;q=0.8,en;q=0.4", 2),
    ("it-IT,it;q=0.9,en;q=0.5", 3), ("ja,en;q=0.3", 2), ("-", 3),
]

PUBLIC = {
    "seed": 4417,
    "first_id": 1,
    "start": "2027-05-03T00:00:00+00:00",
    "end": "2027-05-04T18:00:00+00:00",
    "books": 700, "book_heads": (10, 70, 12), "popular_books": 220, "authors": 300, "popular_authors": 90, "queries": 40,
    "rate_day": 12, "rate_night": 4, "day": (7, 23),
    "langs": LANGS,
    "click_param": "fbclid",
    "purge_every": 9, "author_purge_every": 90,
    "stops": [("2027-05-03T11:00:03+00:00", "2027-05-03T11:00:05+00:00"), ("2027-05-03T13:58:30+00:00", "2027-05-03T14:00:05+00:00")],
    "partner": {"from": "2027-05-03T17:00:00+00:00", "chance": (3, 100), "values": ["sidebar", "footer", "card"]},
    "campaign": {"from": "2027-05-04T06:30:00+00:00", "chance": (30, 100), "burst_min": 90, "burst_rate": 6},
    "events": [
        ("2027-05-03T00:00:00+00:00", "started config=r041"),
        ("2027-05-03T09:00:00+00:00", "config reload rev=42"),
        ("2027-05-03T11:00:03+00:00", "stopping"),
        ("2027-05-03T11:00:05+00:00", "started config=r042"),
        ("2027-05-03T13:58:30+00:00", "stopping"),
        ("2027-05-03T14:00:05+00:00", "started config=r042"),
        ("2027-05-03T20:00:00+00:00", "config reload rev=43"),
        ("2027-05-04T09:20:00+00:00", "cache flush"),
    ],
    "incident": ("2027-05-04T03:10:00+00:00", "2027-05-04T03:45:00+00:00"),
}
