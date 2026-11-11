"""Plays out the club register that produces data/.

generate(out, seed, **options) writes members.json, aliases.json, payments.csv,
audit.jsonl, settings.json and keep_apart.csv. The output depends only on the
seed and the options.

People sign up more than once: at the front desk, online, and through the 2019
import of the old spreadsheet (DD/MM/YYYY days, `;` tags, date-only update
times). Households share a landline and often an email address; a few parents
share their child's full name. Earlier merges left numbers in aliases.json,
and payments and the secretary's keep_apart.csv still name some of them.
"""

import csv
import io
import json
import random
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

GIVEN = ["Anna", "Ben", "Chloé", "Dylan", "Émile", "Fatima", "Grace", "Hamza", "Isla", "Jakub", "Karin", "Liam",
         "Maëlle", "Noah", "Olga", "Priya", "Quinn", "Rhys", "Siân", "Tomás", "Uma", "Viktor", "Wren", "Yusuf",
         "Zoë", "Mary-Kate", "Jean-Luc", "Saoirse", "Niamh", "Søren", "Aoife", "Bríd", "Conor", "Dara", "Eilís",
         "Finn", "Gráinne", "Hugo", "Inés", "José", "Kai", "Lucía", "Mateo", "Nadia", "Oisín", "Pía", "Ruairí",
         "Sean", "Théo", "Ula"]
FAMILY = ["Smith", "O'Neill", "Kowalska", "Nguyen", "García", "Müller", "Ó Briain", "van der Berg", "Okafor",
          "Jones", "Lee", "Murphy", "Brennan", "Haddad", "Fitzgerald-Ryan", "D'Souza", "Novak", "Sato", "Ali",
          "Evans", "Byrne", "Kelly", "Doyle", "Walsh", "Moreau", "Rossi", "Lindqvist", "Kaczmarek", "Ibáñez",
          "MacCárthaigh", "Dubois", "Petrov", "Hughes", "Quinlan", "Ferreira", "Schäfer"]
NICK = {"Ben": "Benjamin", "Liam": "William", "Sean": "Seán", "Kai": "Kaito", "Finn": "Fionn", "Hugo": "Hugh",
        "Dara": "Darragh", "Conor": "Connor", "Anna": "Ann", "Grace": "Gracie"}
OTHER_DOMAINS = ["outlook.com", "yahoo.co.uk", "icloud.com", "proton.me", "btinternet.com", "hotmail.com", "eircom.net"]
TAGS = ["swim", "row", "junior", "masters", "coach", "volunteer", "committee", "life"]
AMOUNTS = ["45.00", "90.00", "25.00", "12.50", "180.00"]
OPERATORS = ["desk", "online", "secretary", "cli"]

DEFAULTS = {
    "persons": 170,
    "country": "44",
    "trunk": "0",
    "mobile_lead": "7",
    "dotless": ["gmail.com", "googlemail.com"],
    "domain_aliases": {"googlemail.com": "gmail.com"},
    "dup": 0.30,
    "dup2": 0.08,
    "households": 14,
    "juniors": 3,
    "namesakes": 3,
    "imports": 0.25,
    "ghosts": 18,
    "payments": 160,
    "audit": 60,
    "close": 0.35,
    "no_dob": 0.2,
}

START = datetime(2012, 1, 1, tzinfo=timezone.utc)
END = datetime(2026, 10, 31, 18, 0, tzinfo=timezone.utc)
IMPORT_AT = datetime(2019, 4, 1, 9, 0, tzinfo=timezone.utc)
APP_SINCE = datetime(2023, 3, 1, tzinfo=timezone.utc)


def ascii_fold(text):
    t = unicodedata.normalize("NFKD", text)
    return "".join(c for c in t if not unicodedata.combining(c))


def local_part(given, family, rng):
    g = "".join(c for c in ascii_fold(given).lower() if c.isalnum())
    f = "".join(c for c in ascii_fold(family).lower() if c.isalnum())
    form = rng.choice(["g.f", "gf", "g1.f", "f.g", "gf#", "g_f"])
    out = {"g.f": f"{g}.{f}", "gf": f"{g}{f}", "g1.f": f"{g[0]}.{f}", "f.g": f"{f}.{g}",
           "gf#": f"{g}{f}{rng.randint(1, 99)}", "g_f": f"{g}_{f}"}[form]
    return out


class World:
    def __init__(self, seed, opts):
        self.rng = random.Random(seed)
        self.o = opts
        self.records = []
        self.used_nsn = set()

    # values ---------------------------------------------------------------

    def nsn(self, lead):
        while True:
            n = lead + "".join(str(self.rng.randint(0, 9)) for _ in range(9))
            if n not in self.used_nsn:
                self.used_nsn.add(n)
                return n

    def domain(self):
        o, rng = self.o, self.rng
        special = list(o["dotless"]) + list(o["domain_aliases"])
        if special and rng.random() < 0.4:
            return rng.choice(sorted(set(special)))
        return rng.choice(OTHER_DOMAINS)

    def phone_text(self, nsn, style=None):
        o, rng = self.o, self.rng
        cc, tr = o["country"], o["trunk"]
        styles = ["nat", "nat", "compact", "intl", "intl", "intl00", "dashed", "paren", "dots"]
        if tr == "0":
            styles.append("intl_trunk")
        style = style or rng.choice(styles)
        return {
            "nat": f"{tr}{nsn[:4]} {nsn[4:]}",
            "compact": f"{tr}{nsn}",
            "intl": f"+{cc} {nsn[:4]} {nsn[4:]}",
            "intl_trunk": f"+{cc} (0){nsn[:4]} {nsn[4:]}",
            "intl00": f"00{cc} {nsn}",
            "dashed": f"{tr}{nsn[:4]}-{nsn[4:7]}-{nsn[7:]}",
            "paren": f"({tr}{nsn[:4]}) {nsn[4:]}",
            "dots": f"+{cc}.{nsn[:3]}.{nsn[3:6]}.{nsn[6:]}",
            "bare": nsn,
        }[style]

    def when(self, lo, hi):
        span = int((hi - lo).total_seconds())
        return lo + timedelta(seconds=self.rng.randrange(0, max(1, span)) // 60 * 60)

    def updated_text(self, t, form=None):
        if form is None:
            form = "offset" if t >= APP_SINCE else "z"
        if form == "z":
            return t.strftime("%Y-%m-%dT%H:%M:%SZ")
        if form == "day":
            return t.strftime("%Y-%m-%d")
        off = 1 if 4 <= t.month <= 9 else 0
        local = t + timedelta(hours=off)
        return local.strftime("%Y-%m-%dT%H:%M:%S") + f"+0{off}:00"

    # people ---------------------------------------------------------------

    def person(self, family=None, given=None, household=None):
        rng = self.rng
        given = given or rng.choice(GIVEN)
        family = family or rng.choice(FAMILY)
        born = None if rng.random() < self.o["no_dob"] else date(1950, 1, 1) + timedelta(days=rng.randrange(0, 60 * 365))
        return {"given": given, "family": family, "dob": born,
                "email": f"{local_part(given, family, rng)}@{self.domain()}" if rng.random() < 0.9 else "",
                "mobile": self.nsn(self.o["mobile_lead"]) if rng.random() < 0.85 else None,
                "household": household}

    def record(self, p, created, imported=False, **over):
        rng = self.rng
        name = over.pop("name", f"{p['given']} {p['family']}")
        if imported:
            joined = (created - timedelta(days=rng.randrange(30, 15 * 365))).date()
            joined_text = joined.strftime("%d/%m/%Y")
        else:
            joined_text = created.date().isoformat()
        dob = p["dob"]
        dob_text = "" if dob is None else (dob.strftime("%d/%m/%Y") if imported else dob.isoformat())
        phone = ""
        if p["household"] is not None and rng.random() < 0.5:
            phone = self.phone_text(p["household"]["landline"])
        elif p["mobile"]:
            phone = self.phone_text(p["mobile"])
        if imported:
            tags = ";".join(["import-2019"] + sorted(rng.sample(TAGS, rng.randint(0, 2))))
            last = IMPORT_AT if rng.random() < 0.6 else self.when(IMPORT_AT, END)
            updated = self.updated_text(last, "day" if last == IMPORT_AT else None)
        else:
            tags = rng.sample(TAGS, rng.randint(0, 3))
            last = self.when(created, END) if rng.random() < 0.7 else created
            updated = self.updated_text(last)
        expires = "" if rng.random() < 0.15 else (date(2019, 1, 1) + timedelta(days=rng.randrange(0, 9 * 365))).isoformat()
        r = {"name": name, "email": p["email"], "phone": phone, "dob": dob_text, "joined": joined_text,
             "expires": expires, "marketing": rng.choice(["yes", "yes", "no", "", ""]), "tags": tags,
             "updated": updated, "_created": created, "_last": last, "_person": id(p), "_imported": imported}
        r.update(over)
        self.records.append(r)
        return r

    def created(self):
        return self.when(START, END - timedelta(days=30))

    # variations for a second sign-up --------------------------------------

    def vary_email(self, email):
        rng, o = self.rng, self.o
        if not email:
            return email
        local, domain = email.split("@")
        k = rng.choice(["same", "case", "plus", "dots", "alias", "other", "empty", "case", "plus", "dots"])
        if k == "case":
            return f" {local.capitalize()}@{domain.upper()} " if rng.random() < 0.5 else email.upper()
        if k == "plus":
            return f"{local}+{rng.choice(['club', 'swim', 'row', 'sub2024'])}@{domain}"
        if k == "dots":
            bare = local.replace(".", "")
            cut = rng.randint(1, max(1, len(bare) - 1))
            return f"{bare[:cut]}.{bare[cut:]}@{domain}" if rng.random() < 0.7 else f"{bare}@{domain}"
        if k == "alias":
            back = {v: k2 for k2, v in o["domain_aliases"].items()}
            if domain in back:
                return f"{local}@{back[domain]}"
            if domain in o["domain_aliases"]:
                return f"{local}@{o['domain_aliases'][domain]}"
            return email
        if k == "other":
            return f"{local.replace('.', '')}{rng.randint(1, 9)}@{rng.choice(OTHER_DOMAINS)}"
        if k == "empty":
            return ""
        return email

    def vary_name(self, p):
        rng = self.rng
        name = f"{p['given']} {p['family']}"
        k = rng.choice(["same", "same", "upper", "fold", "space", "hyphen", "apostrophe", "married", "nick"])
        if k == "upper":
            return name.upper()
        if k == "fold":
            return ascii_fold(name)
        if k == "space":
            return f" {p['given']}  {p['family']}"
        if k == "hyphen":
            return name.replace("-", " ") if "-" in name else name.replace(" ", "-", 1)
        if k == "apostrophe":
            return name.replace("'", "") if "'" in name else name.lower()
        if k == "married":
            return f"{p['given']} {rng.choice(FAMILY)}"
        if k == "nick":
            return f"{NICK.get(p['given'], p['given'])} {p['family']}"
        return name

    def duplicate(self, p, base):
        rng = self.rng
        imported = not base["_imported"] and rng.random() < self.o["imports"]
        created = IMPORT_AT if imported else self.created()
        over = {"name": self.vary_name(p), "email": self.vary_email(p["email"])}
        r = self.record(p, created, imported=imported, **over)
        if not imported:
            k = rng.random()
            if k < 0.3 and p["dob"] is not None:
                r["dob"] = ""
        if rng.random() < 0.25:
            r["phone"] = ""
        elif p["mobile"] and rng.random() < 0.3:
            r["phone"] = self.phone_text(p["mobile"], rng.choice(["bare", "intl", "intl00", "compact"]))
        return r

    def close_times(self, group):
        """Two records of one person updated within an hour or so, written in different forms."""
        rng = self.rng
        a, b = rng.sample(group, 2)
        t = self.when(max(APP_SINCE, a["_created"], b["_created"]), END)
        a["updated"] = self.updated_text(t, "offset")
        if rng.random() < 0.3:
            b["updated"] = self.updated_text(t, "z")
        else:
            b["updated"] = self.updated_text(t + timedelta(minutes=rng.choice([-50, -20, 10, 25, 40])), "z")


def build(seed, opts):
    w = World(seed, opts)
    rng = w.rng
    groups = []
    for _ in range(opts["persons"]):
        p = w.person()
        imported = rng.random() < opts["imports"]
        base = w.record(p, IMPORT_AT if imported else w.created(), imported=imported)
        group = [base]
        if rng.random() < opts["dup"]:
            group.append(w.duplicate(p, base))
            if rng.random() < opts["dup2"] / opts["dup"]:
                group.append(w.duplicate(p, base))
        if len(group) > 1:
            groups.append(group)
            if rng.random() < opts["close"]:
                w.close_times(group)
    for _ in range(opts["households"]):
        family = rng.choice(FAMILY)
        home = {"landline": w.nsn("2")}
        shared = f"{local_part('the', family, rng)}@{w.domain()}" if rng.random() < 0.6 else None
        names = rng.sample(GIVEN, rng.randint(2, 4))
        for g in names:
            p = w.person(family=family, given=g, household=home)
            if shared and rng.random() < 0.8:
                p["email"] = shared
            r = w.record(p, w.created())
            if rng.random() < 0.6:
                r["phone"] = w.phone_text(home["landline"])
    apart = []
    for _ in range(opts["juniors"]):
        family = rng.choice(FAMILY)
        given = rng.choice(GIVEN)
        home = {"landline": w.nsn("2")}
        email = f"{local_part(given, family, rng)}@{w.domain()}"
        parent = w.person(family=family, given=given, household=home)
        child = w.person(family=family, given=given, household=home)
        parent["dob"] = date(1965, 1, 1) + timedelta(days=rng.randrange(0, 20 * 365))
        child["dob"] = parent["dob"] + timedelta(days=rng.randrange(22 * 365, 35 * 365))
        parent["email"] = child["email"] = email
        rp = w.record(parent, w.created())
        rc = w.record(child, w.created())
        rp["phone"] = w.phone_text(home["landline"])
        rc["phone"] = w.phone_text(home["landline"])
        if rng.random() < 0.8:
            name = f"{given} {family}"
            again = w.record(parent, w.created(), name=rng.choice([name, name.upper(), ascii_fold(name)]))
            again["dob"] = ""
            again["email"] = w.vary_email(email) or email
            again["phone"] = w.phone_text(home["landline"])
            again["_person"] = rp["_person"]
    for _ in range(opts["namesakes"]):
        given, family = rng.choice(GIVEN), rng.choice(FAMILY)
        home = {"landline": w.nsn("2")}
        a = w.person(family=family, given=given, household=home)
        b = w.person(family=family, given=given, household=home)
        b["dob"] = None
        ra, rb = w.record(a, w.created()), w.record(b, w.created())
        ra["phone"] = w.phone_text(home["landline"])
        rb["phone"] = w.phone_text(home["landline"])
        apart.append((ra, rb, "namesakes, checked by phone"))
    return w, groups, apart


def number_records(w, opts):
    rng = w.rng
    recs = sorted(w.records, key=lambda r: (r["_created"], rng.random()))
    ghosts = set()
    numbered = []
    total = len(recs) + opts["ghosts"]
    ghost_slots = set(rng.sample(range(1, total + 1), opts["ghosts"]))
    it = iter(recs)
    for k in range(1, total + 1):
        if k in ghost_slots:
            ghosts.add(k)
            continue
        r = next(it)
        r["n"] = k
        numbered.append(r)
    return numbered, sorted(ghosts)


def generate(out: Path, seed: int, **options) -> None:
    opts = {**DEFAULTS, **options}
    w, groups, apart = build(seed, opts)
    rng = w.rng
    recs, ghosts = number_records(w, opts)
    by_n = {r["n"]: r for r in recs}
    dup_side = [r["n"] for g in groups for r in g]
    aliases = {}
    pinned = rng.sample(ghosts, min(len(apart), len(ghosts)))
    for g, (ra, _, _) in zip(pinned, apart):
        aliases[g] = ra["n"]
    for g in ghosts:
        if g in aliases:
            continue
        later = [n for n in dup_side if n > g] if rng.random() < 0.5 else []
        pool = later or [n for n in by_n if n > g] or list(by_n)
        aliases[g] = rng.choice(sorted(pool))

    def typed(n):
        k = rng.random()
        if k < 0.7:
            return f"M-{n:04d}"
        if k < 0.85:
            return f"M-{n}"
        return f"m-{n:04d}"

    out.mkdir(parents=True, exist_ok=True)
    members = []
    for r in sorted(recs, key=lambda r: r["n"]):
        members.append({"id": f"M-{r['n']:04d}", "name": r["name"], "email": r["email"], "phone": r["phone"],
                        "dob": r["dob"], "joined": r["joined"], "expires": r["expires"], "marketing": r["marketing"],
                        "tags": r["tags"], "updated": r["updated"]})
    (out / "members.json").write_text(json.dumps({"format": 3, "members": members}, indent=2, ensure_ascii=False) + "\n",
                                      encoding="utf-8")

    alias_doc = {}
    for k in sorted(aliases):
        key = f"M-{k}" if k < 100 else f"M-{k:04d}"
        alias_doc[key] = f"M-{aliases[k]:04d}"
    (out / "aliases.json").write_text(json.dumps(alias_doc, indent=2) + "\n", encoding="utf-8")

    pays = []
    every = sorted(by_n) + ghosts
    for _ in range(opts["payments"]):
        n = rng.choice(every)
        first = by_n[n]["_created"].date() if n in by_n else date(2015, 1, 1)
        day = first + timedelta(days=rng.randrange(0, max(1, (END.date() - first).days)))
        pays.append((day, rng.random(), n))
    pays.sort()
    buf = io.StringIO()
    wr = csv.writer(buf, lineterminator="\n")
    wr.writerow(["payment", "member", "day", "amount"])
    for i, (day, _, n) in enumerate(pays, start=1):
        wr.writerow([f"P-{i:05d}", f"M-{n}" if n in ghosts and rng.random() < 0.5 else typed(n), day.isoformat(),
                     rng.choice(AMOUNTS)])
    (out / "payments.csv").write_text(buf.getvalue(), encoding="utf-8")

    seq = rng.randint(3000, 6000)
    at = datetime(2025, 1, 6, 9, 0, tzinfo=timezone.utc)
    lines = []
    for _ in range(opts["audit"]):
        at += timedelta(minutes=rng.randint(30, 9000))
        n = rng.choice(sorted(by_n))
        op = rng.choice(["edit", "renew", "pay"])
        e = {"seq": seq, "at": at.strftime("%Y-%m-%dT%H:%M:%SZ"), "op": op, "by": rng.choice(OPERATORS),
             "member": f"M-{n:04d}"}
        if op == "edit":
            f = rng.choice(["email", "phone", "marketing"])
            e["changes"] = {f: ["", by_n[n][f] if isinstance(by_n[n][f], str) else ""],
                            "updated": ["2024-01-01T00:00:00Z", e["at"]]}
        elif op == "renew":
            e["changes"] = {"expires": ["", f"{at.year + 1}-{at.month:02d}-01"], "updated": ["2024-01-01T00:00:00Z", e["at"]]}
        else:
            e["payment"], e["amount"] = f"P-{rng.randint(1, opts['payments']):05d}", rng.choice(AMOUNTS)
        lines.append(json.dumps(e, separators=(",", ":"), ensure_ascii=False))
        seq += rng.choice([1, 1, 1, 2])
    (out / "audit.jsonl").write_text("".join(line + "\n" for line in lines), encoding="utf-8")

    settings = {"phone": {"country": opts["country"], "trunk": opts["trunk"]},
                "email": {"dotless_domains": list(opts["dotless"]), "domain_aliases": dict(opts["domain_aliases"])}}
    (out / "settings.json").write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")

    rev = {}
    for g, n in aliases.items():
        rev.setdefault(n, []).append(g)
    rows = []
    for ra, rb, note in apart:
        a, b = ra["n"], rb["n"]
        ta = f"M-{rng.choice(sorted(rev[a]))}" if a in rev and rng.random() < 0.8 else typed(a)
        rows.append((ta, typed(b), note))
    for _ in range(3):
        a, b = rng.sample(sorted(by_n), 2)
        rows.append((typed(a), typed(b), "different people"))
    if groups:
        g = rng.choice(groups)
        rows.append((typed(g[0]["n"]), typed(g[1]["n"]), "different people, same address"))
    gone = max(list(by_n) + ghosts) + rng.randint(5, 40)
    rows.append((typed(gone), typed(rng.choice(sorted(by_n))), "left the club"))
    rng.shuffle(rows)
    buf = io.StringIO()
    wr = csv.writer(buf, lineterminator="\n")
    wr.writerow(["first", "second", "note"])
    wr.writerows(rows)
    (out / "keep_apart.csv").write_text(buf.getvalue(), encoding="utf-8")
