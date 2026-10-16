"""Writes a tally store: four collections with schemas and part files.

Usage: python3 storegen.py OUT_DIR SEED

The output depends only on SEED.
"""

import json
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

FIRST = ["Ana", "Bo", "Chloé", "Dmitri", "Eva", "Farid", "Grace", "Hiro", "Ines", "Jonas", "Kai", "Lena", "Mateo", "Nora",
         "Olu", "Priya", "Quinn", "Rosa", "Sven", "Tomás", "Uma", "Vik", "Wen", "Xavier", "Yara", "Zoë", "ana", "émile"]
LAST = ["Smith", "O'Brien", "Müller", "Nakamura", "García", "Okafor", "Lund", "Kowalski", "Dubois", "Rossi", "Chen",
        "Svensson", "Silva", "de Vries", "Novak", "Haddad", "Ivanova", "Byrne", "smith", "Ñúñez"]
COUNTRIES = ["DE", "FR", "US", "GB", "IN", "ES", "SE", "JP", "BR", "NL", "PL", "CH"]
CITIES = ["Berlin", "Paris", "Austin", "Leeds", "Pune", "Sevilla", "Malmö", "Osaka", "Recife", "Utrecht", "Kraków",
          "Zürich", "St. Gallen", "Saint-Denis", "Washington, D.C.", "'s-Hertogenbosch", "Frankfurt am Main"]
SEGMENTS = ["retail", "wholesale", "public", "Retail", "partner"]
STATUSES = ["open", "paid", "shipped", "cancelled", "refunded", "on hold"]
CHANNELS = ["web", "phone", "store", "partner", "Web"]
CATEGORIES = ["tools", "garden", "kitchen", "office", "Toys", "outdoor", "bath", "lighting"]
KINDS = ["login", "logout", "purchase", "refund", "view", "error", "export"]
SOURCES = ["api", "batch", "ui", "mobile"]
NOTES = [
    "call before delivery", "leave at door, side entrance", 'said "urgent"', "  leading spaces", "trailing space ",
    "two\nlines", "carriage\r\nreturn", "semi;colon", "pipe|char", "tab\tinside", "", "NULL", "\\N", "-", "n/a",
    "comma, and \"quote\"", "Ünïcödé ✓", "日本語のメモ", "'single'", "a,b,c", "\ttab first", "ends with tab\t",
    "plain note", "fragile", "gift wrap", "back order", "VIP", "repeat customer",
]
TAGS = ["new", "sale", "eco", "bulk", "new,sale", "clearance", "", "limited \"edition\"", "best seller"]


def dec(value: float, scale: int) -> str:
    text = f"{value:.{scale}f}"
    return text[1:] if text.startswith("-") and not text.strip("-0.") else text


def ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def maybe(rng, p, value):
    return None if rng.random() < p else value


def schema(name, key, fields):
    return {"collection": name, "key": key, "fields": [dict(zip(("name", "type", "scale", "nullable"), f)) for f in fields]}


SCHEMAS = {
    "customers": schema("customers", "id", [
        ("id", "int", 0, False), ("name", "string", 0, False), ("email", "string", 0, True), ("country", "string", 0, False),
        ("segment", "string", 0, True), ("signup", "date", 0, False), ("vip", "bool", 0, True),
        ("credit_limit", "decimal", 2, True), ("address.city", "string", 0, True), ("address.postcode", "string", 0, True),
        ("notes", "string", 0, True)]),
    "orders": schema("orders", "id", [
        ("id", "int", 0, False), ("customer_id", "int", 0, False), ("placed", "datetime", 0, False), ("status", "string", 0, False),
        ("total", "decimal", 2, False), ("discount_rate", "decimal", 3, True), ("items", "int", 0, False),
        ("channel", "string", 0, True), ("shipped", "date", 0, True), ("priority", "bool", 0, False),
        ("balance", "decimal", 2, True), ("note", "string", 0, True)]),
    "products": schema("products", "sku", [
        ("sku", "string", 0, False), ("title", "string", 0, False), ("category", "string", 0, True), ("price", "decimal", 2, False),
        ("weight_kg", "decimal", 3, True), ("stock", "int", 0, False), ("launched", "date", 0, True), ("active", "bool", 0, False),
        ("tags", "string", 0, True)]),
    "events": schema("events", "id", [
        ("id", "int", 0, False), ("at", "datetime", 0, False), ("kind", "string", 0, False), ("user", "string", 0, True),
        ("value", "decimal", 4, True), ("amount", "int", 0, True), ("payload.source", "string", 0, True),
        ("payload.ref", "string", 0, True)]),
}
for s in SCHEMAS.values():
    for f in s["fields"]:
        if f["type"] != "decimal":
            del f["scale"]
        if not f["nullable"]:
            del f["nullable"]


def big_amount(rng) -> float:
    return rng.choice([rng.uniform(0, 999), rng.uniform(1000, 99999), rng.uniform(100000, 9999999), rng.uniform(10000000, 2000000000)])


def customer(rng, i) -> dict:
    r = {"id": i, "name": f"{rng.choice(FIRST)} {rng.choice(LAST)}", "country": rng.choice(COUNTRIES),
         "signup": (date(2019, 1, 1) + timedelta(days=rng.randint(0, 2400))).isoformat()}
    if rng.random() < 0.8:
        r["email"] = f"{r['name'].split()[0].lower()}{i}@example.com"
    elif rng.random() < 0.5:
        r["email"] = None
    seg = maybe(rng, 0.2, rng.choice(SEGMENTS))
    if seg is not None or rng.random() < 0.5:
        r["segment"] = seg
    r["vip"] = maybe(rng, 0.25, rng.random() < 0.3)
    r["credit_limit"] = maybe(rng, 0.2, dec(rng.choice([0, 500, 1000, 2500, 10000, 25000, 150000, 1234567.5, rng.uniform(0, 99999)]), 2))
    if rng.random() < 0.85:
        addr = {"city": maybe(rng, 0.1, rng.choice(CITIES))}
        if rng.random() < 0.8:
            addr["postcode"] = rng.choice(["10115", "75001", "73301", "LS1 4AP", "411001", "41001", "211 22", "530-0001", "", "0000"])
        r["address"] = addr
    if rng.random() < 0.55:
        r["notes"] = rng.choice(NOTES)
    return r


def order(rng, i, customers) -> dict:
    placed = datetime(2025, 1, 1) + timedelta(seconds=rng.randint(0, 600 * 86400))
    if rng.random() < 0.1:
        placed = placed.replace(hour=rng.choice([0, 12]), minute=rng.choice([0, 5, 30]))
    total = rng.choice([rng.uniform(1, 200), rng.uniform(200, 5000), rng.uniform(5000, 250000)])
    r = {"id": i, "customer_id": rng.choice(customers), "placed": ts(placed), "status": rng.choice(STATUSES),
         "total": dec(total, 2), "items": rng.randint(1, 40), "priority": rng.random() < 0.2}
    if rng.random() < 0.6:
        r["discount_rate"] = maybe(rng, 0.3, dec(rng.choice([0, 0.05, 0.1, 0.125, 0.2, 0.333]), 3))
    if rng.random() < 0.85:
        r["channel"] = maybe(rng, 0.15, rng.choice(CHANNELS))
    if r["status"] in ("shipped", "paid") and rng.random() < 0.8:
        r["shipped"] = (placed.date() + timedelta(days=rng.randint(0, 9))).isoformat()
    r["balance"] = maybe(rng, 0.2, dec(rng.choice([0, -total, total / 3, -rng.uniform(1, 9999999), rng.uniform(0, 1500000)]), 2))
    if rng.random() < 0.4:
        r["note"] = rng.choice(NOTES)
    return r


def product(rng, i) -> dict:
    sku = f"{rng.choice('ABCDEFGH')}{rng.choice('ABCDEFGH')}-{1000 + i * 7}"
    r = {"sku": sku, "title": f"{rng.choice(['Hammer', 'Rake', 'Pan', 'Stapler', 'Kite', 'Tent', 'Towel', 'Lamp'])} {rng.choice(['Pro', 'mini', '2000', 'XL, deluxe', '\"Classic\"', 'Öko'])}",
         "price": dec(rng.choice([rng.uniform(0.5, 40), rng.uniform(40, 900), rng.uniform(900, 12000)]), 2),
         "stock": rng.randint(-50, 25000), "active": rng.random() < 0.8}
    if rng.random() < 0.9:
        r["category"] = maybe(rng, 0.1, rng.choice(CATEGORIES))
    r["weight_kg"] = maybe(rng, 0.25, dec(rng.uniform(0.001, 1500), 3))
    if rng.random() < 0.8:
        r["launched"] = maybe(rng, 0.1, (date(2015, 1, 1) + timedelta(days=rng.randint(0, 4000))).isoformat())
    if rng.random() < 0.5:
        r["tags"] = rng.choice(TAGS)
    return r


def event(rng, i) -> dict:
    at = datetime(2025, 6, 1) + timedelta(seconds=rng.randint(0, 200 * 86400))
    r = {"id": i, "at": ts(at), "kind": rng.choice(KINDS)}
    if rng.random() < 0.8:
        r["user"] = maybe(rng, 0.1, rng.choice(FIRST).lower() + str(rng.randint(1, 99)))
    r["value"] = maybe(rng, 0.3, dec(rng.uniform(-50, 50) if rng.random() < 0.7 else rng.uniform(-999999, 999999), 4))
    r["amount"] = maybe(rng, 0.3, int(big_amount(rng)) * rng.choice([1, 1, -1]))
    if rng.random() < 0.75:
        payload = {"source": maybe(rng, 0.1, rng.choice(SOURCES))}
        if rng.random() < 0.6:
            payload["ref"] = rng.choice(["R-1", "R-10", "R-2", "r-1", "", "ref,with,commas", "x\"y"]) + str(rng.randint(0, 9))
        r["payload"] = payload
    return r


def write_parts(root: Path, rng: random.Random, records: list, key: str, make) -> None:
    lines = []
    for r in records:
        lines.append(json.dumps(r, ensure_ascii=False))
    keys = [r[key] for r in records]
    extra = []
    for k in rng.sample(keys, max(3, len(keys) // 25)):
        extra.append(json.dumps({"$delete": k}))
    for k in rng.sample(keys, max(3, len(keys) // 20)):
        newer = make(k)
        extra.append(json.dumps(newer, ensure_ascii=False))
    rng.shuffle(extra)
    parts = rng.randint(3, 5)
    size = len(lines) // parts + 1
    chunks = [lines[i:i + size] for i in range(0, len(lines), size)]
    # Later parts carry deletes and replacements of records from earlier parts.
    for j, line in enumerate(extra):
        target = 1 + j % (len(chunks) - 1)
        chunks[target].insert(rng.randint(0, len(chunks[target])), line)
    for n, chunk in enumerate(chunks, 1):
        (root / f"part-{n:04d}.jsonl").write_text("\n".join(chunk) + "\n", encoding="utf-8")


def generate(out: Path, seed: int, scale: float = 1.0) -> None:
    rng = random.Random(seed)
    out = Path(out)
    counts = {"customers": int(900 * scale), "orders": int(3600 * scale), "products": int(500 * scale), "events": int(2800 * scale)}
    cust_ids = rng.sample(range(1000, 99999), counts["customers"])
    builders = {
        "customers": (lambda k: customer(rng, k), cust_ids),
        "orders": (lambda k: order(rng, k, cust_ids), list(range(500000, 500000 + counts["orders"] * 3, 3))),
        "products": (None, None),
        "events": (lambda k: event(rng, k), list(range(1, counts["events"] + 1))),
    }
    for name, sch in SCHEMAS.items():
        root = out / name
        root.mkdir(parents=True, exist_ok=True)
        (root / "schema.json").write_text(json.dumps(sch, indent=2) + "\n", encoding="utf-8")
        if name == "products":
            records = [product(rng, i) for i in range(counts["products"])]
            by_sku = {r["sku"]: r for r in records}
            records = list(by_sku.values())

            def make(k, rng=rng):
                r = product(rng, 0)
                r["sku"] = k
                return r
            write_parts(root, rng, records, "sku", make)
        else:
            fn, keys = builders[name]
            records = [fn(k) for k in keys]
            write_parts(root, rng, records, "id", fn)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    generate(Path(sys.argv[1]), int(sys.argv[2]))
