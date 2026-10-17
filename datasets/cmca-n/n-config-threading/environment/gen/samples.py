"""Shipment files and settings files for quoter. Output depends only on the seed."""

import random
from pathlib import Path

COUNTRIES = [
    "AT", "BE", "BG", "CH", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR", "GB", "GR", "HR", "HU", "IE", "IS",
    "IT", "LI", "LT", "LU", "LV", "MT", "NL", "NO", "PL", "PT", "RO", "RS", "SE", "SI", "SK", "TR", "UA", "US",
    "CA", "JP", "AU", "GI",
]
ORIGINS = ["DE", "DE", "DE", "FR", "NL", "GB", "IT", "PL", "ES", "SE"]
REMOTE = {
    "GB": ["HS1 2AB", "ZE1 0AA", "KW15 1AB"],
    "FR": ["20000", "20090"],
    "DE": ["18565", "25846"],
    "IT": ["07100", "90121", "98122"],
    "ES": ["35001", "38001", "07001"],
    "NO": ["9300", "9500"],
    "PT": ["9000-018", "9500-100"],
    "DK": ["3700", "3900"],
    "GR": ["81100", "84300"],
    "FI": ["22100"],
}


def postcode(rng: random.Random, cc: str) -> str:
    if cc in REMOTE and rng.random() < 0.12:
        return rng.choice(REMOTE[cc])
    letters = "ABDEFGHJLNPRSTUWXYZ"
    if cc == "GB":
        return f"{rng.choice(['SW', 'EC', 'M', 'B', 'LS', 'G', 'CF'])}{rng.randint(1, 9)} {rng.randint(1, 9)}{rng.choice(letters)}{rng.choice(letters)}"
    if cc == "NL":
        return f"{rng.randint(1000, 9999)} {rng.choice(letters)}{rng.choice(letters)}"
    if cc == "PT":
        return f"{rng.randint(1000, 8999)}-{rng.randint(100, 999)}"
    if cc == "PL":
        return f"{rng.randint(10, 99)}-{rng.randint(100, 999)}"
    if cc == "CA":
        return f"{rng.choice('KLMNPRT')}{rng.randint(1, 9)}{rng.choice('ABCEGH')} {rng.randint(1, 9)}{rng.choice('ABCEGH')}{rng.randint(1, 9)}"
    if cc in ("IE", "MT", "LI"):
        return f"{rng.choice(['D', 'T', 'V'])}{rng.randint(10, 99)}"
    if cc in ("AT", "BE", "BG", "CH", "CY", "DK", "HU", "LU", "NO", "SI", "AU"):
        return str(rng.randint(1000, 9999))
    return str(rng.randint(10000, 99999))


def weight(rng: random.Random, imperial: bool) -> str:
    kind = rng.random()
    if kind < 0.25:
        kg = rng.uniform(0.1, 1.0)
    elif kind < 0.75:
        kg = rng.uniform(1.0, 12.0)
    elif kind < 0.95:
        kg = rng.uniform(12.0, 45.0)
    else:
        kg = rng.uniform(45.0, 420.0)
    if imperial:
        kg = kg * 2.2
    return f"{kg:.{rng.choice([1, 2, 2, 3])}f}"


def dims(rng: random.Random, imperial: bool) -> str:
    if rng.random() < 0.3:
        return ""
    sides = sorted((rng.randint(5, 70) for _ in range(3)), reverse=True)
    if rng.random() < 0.07:
        sides[0] = rng.randint(110, 190)
    if imperial:
        sides = [max(2, round(s / 2.54)) for s in sides]
    rng.shuffle(sides)
    sep = rng.choice(["x", "x", "X", "*"])
    return sep.join(str(s) for s in sides)


BAD_ROWS = [
    ("XX-1234", "weight"),
    ("DE-ABC!", "weight"),
    ("FR-75001", "0"),
    ("FR-75001", "1200"),
    ("GB-12345", "weight"),
    ("ZZ-10115", "weight"),
    ("DE-10115", "abc"),
]


def shipments(rng: random.Random, rows: int, imperial: bool = False, bad: int = 3) -> str:
    out = ["id,from,to,weight,dims,residential,value"]
    made = []
    for i in range(rows):
        ident = f"S{rng.randint(100000, 999999)}"
        if made and rng.random() < 0.08:
            # Repeated shipments are common in real files.
            out.append(f"{ident},{rng.choice(made)}")
            continue
        origin = rng.choice(ORIGINS)
        dest = rng.choice(COUNTRIES if rng.random() < 0.6 else [origin] + ORIGINS)
        res = rng.choice(["", "", "yes", "no", "y", "1"])
        value = rng.choice(["", "", "", "", "120", "45.50", "800", "2500", "30000"])
        body = f"{origin}-{postcode(rng, origin)},{dest}-{postcode(rng, dest)},{weight(rng, imperial)},{dims(rng, imperial)},{res},{value}"
        made.append(body)
        out.append(f"{ident},{body}")
    for _ in range(bad):
        to, w = rng.choice(BAD_ROWS)
        w = weight(rng, imperial) if w == "weight" else w
        pos = rng.randint(1, len(out))
        out.insert(pos, f"S{rng.randint(100000, 999999)},DE-10115,{to},{w},,,")
    return "\n".join(out) + "\n"


PROFILES = [
    {"currency": "GBP"},
    {"rate_card": "2026"},
    {"fuel_pct": "14.25"},
    {"box_set": "eco"},
    {"discount_tiers": "5:1.5,20:4,80:9"},
    {"csv_delimiter": ";"},
]


def settings_file(profile: dict, comment: str) -> str:
    lines = [f"# {comment}", "[quoter]"]
    for k, v in profile.items():
        lines.append(f"{k} = {v}")
    return "\n".join(lines) + "\n"


def make_samples(seed: int, out: Path, files: int, rows: int) -> list:
    rng = random.Random(seed)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for i in range(files):
        name = f"shipments-{i + 1:02d}.csv"
        (out / name).write_text(shipments(rng, rng.randint(rows // 2, rows)), encoding="utf-8")
        written.append(out / name)
    for i, profile in enumerate(PROFILES):
        name = f"customer-{i + 1}.ini"
        (out / name).write_text(settings_file(profile, f"customer profile {i + 1}"), encoding="utf-8")
        written.append(out / name)
    return written
