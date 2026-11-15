"""Overdue fee statements, following docs/ step by step.

Usage: feesref.py INPUT_DIR OUTPUT_FILE
"""
import configparser
import csv
import io
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
OFFSET = re.compile(r"([+-])(\d\d):(\d\d)")


def cents(text):
    return int((Decimal(text.strip()) * 100).to_integral_value())


def offset_minutes(text):
    m = OFFSET.fullmatch(text.strip())
    sign = -1 if m.group(1) == "-" else 1
    return sign * (int(m.group(2)) * 60 + int(m.group(3)))


def patron_key(text):
    s = re.sub(r"[\s\-]", "", text).upper()
    if s.startswith("P"):
        s = s[1:]
    return int(s)


def day(text):
    return date.fromisoformat(text.strip())


class Policy:
    def __init__(self, path):
        cp = configparser.ConfigParser(interpolation=None)
        cp.read_string(path.read_text(encoding="utf-8-sig"))
        st = cp["statement"]
        self.library = st["library"].strip()
        self.start = day(st["period_start"])
        self.end = day(st["period_end"])
        clock = cp["clock"]
        self.offsets = [(None, offset_minutes(clock["offset"]))]
        for part in clock.get("changes", "").split(";"):
            if not part.strip():
                continue
            when, off = part.split()
            at = datetime.fromisoformat(when.replace("Z", "+00:00")).astimezone(timezone.utc)
            self.offsets.append((at, offset_minutes(off)))
        self.items = {}
        self.categories = {}
        for name in cp.sections():
            kind, _, ident = name.partition(":")
            sec = cp[name]
            if kind.strip() == "item":
                self.items[ident.strip().lower()] = {
                    "loan_days": int(sec["loan_days"]),
                    "renewals": int(sec["renewals"]),
                    "grace_days": int(sec["grace_days"]),
                    "daily": cents(sec["daily"]),
                    "loan_cap": cents(sec["loan_cap"]),
                }
            elif kind.strip() == "category":
                cap = sec["statement_cap"].strip()
                self.categories[ident.strip().lower()] = {
                    "cap": None if cap.lower() == "none" else cents(cap),
                    "discount": int(sec.get("discount", "0").strip() or "0"),
                    "exempt": {x.strip().lower() for x in sec.get("exempt", "").split(",") if x.strip()},
                }

    def local(self, instant):
        off = self.offsets[0][1]
        for at, o in self.offsets[1:]:
            if instant >= at:
                off = o
        return (instant + timedelta(minutes=off)).replace(tzinfo=None)


class Calendar:
    def __init__(self, src):
        self.weekly = {}
        self.order = []
        for row in read_csv(src / "branches.csv"):
            b = row["branch"].strip()
            self.order.append(b)
            self.weekly[b] = {d.strip().lower()[:3] for d in row["open_days"].split()}
        self.specific = {}
        self.every = {}
        for row in read_csv(src / "calendar.csv"):
            text = row["date"].strip()
            first, _, last = text.partition("..")
            a = day(first)
            b = day(last) if last else a
            status = row["status"].strip().lower() == "open"
            target = row["branch"].strip()
            while a <= b:
                if target == "*":
                    self.every[a] = status
                else:
                    self.specific[(target, a)] = status
                a += timedelta(days=1)

    def is_open(self, branch, d):
        if (branch, d) in self.specific:
            return self.specific[(branch, d)]
        if d in self.every:
            return self.every[d]
        return WEEKDAYS[d.weekday()] in self.weekly[branch]

    def next_open(self, branch, d):
        while not self.is_open(branch, d):
            d += timedelta(days=1)
        return d


def read_csv(path):
    text = path.read_bytes().decode("utf-8-sig")
    rows = []
    for row in csv.DictReader(io.StringIO(text, newline="")):
        clean = {(k or "").strip(): (v or "") for k, v in row.items()}
        if any(v.strip() for v in clean.values()):
            rows.append(clean)
    return rows


def read_events(src, policy):
    events = {}
    for p in sorted((src / "exports").iterdir()):
        if not p.is_file():
            continue
        if p.name.endswith(".csv"):
            for row in read_csv(p):
                local = datetime.strptime(row["time"].strip(), "%Y-%m-%d %H:%M")
                add_event(events, row, local)
        elif p.name.endswith(".jsonl"):
            for line in p.read_bytes().decode("utf-8-sig").split("\n"):
                if not line.strip():
                    continue
                obj = json.loads(line)
                at = datetime.fromisoformat(obj["at"].strip().replace("Z", "+00:00")).astimezone(timezone.utc)
                add_event(events, {k: "" if v is None else str(v) for k, v in obj.items()}, policy.local(at))
    return events


def add_event(events, row, local):
    eid = row["event"].strip()
    if eid in events:
        return
    events[eid] = {
        "event": eid,
        "local": local,
        "type": row["type"].strip().lower(),
        "loan": row.get("loan", "").strip(),
        "patron": row.get("patron", "").strip(),
        "item": row.get("item", "").strip(),
        "item_type": row.get("item_type", "").strip().lower(),
        "branch": row.get("branch", "").strip(),
        "via": row.get("via", "").strip().lower(),
        "target": row.get("target", "").strip(),
    }


def category_on(rows, d):
    best = None
    for since, cat in rows:
        if since <= d:
            best = cat
    return best


def half_up(numerator, denominator):
    return (2 * numerator + denominator) // (2 * denominator)


def main(src, dst):
    src = Path(src)
    policy = Policy(src / "policy.ini")
    cal = Calendar(src)
    patrons = {}
    shown = {}
    for row in read_csv(src / "patrons.csv"):
        key = patron_key(row["patron"])
        shown.setdefault(key, row["patron"].strip())
        patrons.setdefault(key, []).append((day(row["since"]), row["category"].strip().lower()))
    for rows in patrons.values():
        rows.sort()
    waivers = []
    for row in read_csv(src / "waivers.csv"):
        if row["status"].strip().lower() != "active":
            continue
        value = row["value"].strip().lower()
        waivers.append((patron_key(row["patron"]), row["loan"].strip(), None if value == "full" else cents(value)))

    events = read_events(src, policy)
    voided = {e["target"] for e in events.values() if e["type"] == "void"}
    live = [e for e in events.values() if e["type"] != "void" and e["event"] not in voided]
    loans = {}
    for e in live:
        if e["type"] == "checkout" and e["local"].date() <= policy.end:
            loans[e["loan"]] = {"out": e, "later": []}
    for e in live:
        if e["type"] in ("renew", "return") and e["loan"] in loans:
            loans[e["loan"]]["later"].append(e)

    entries = {}
    for loan_id, loan in loans.items():
        out = loan["out"]
        item = policy.items[out["item_type"]]
        branch = out["branch"]
        checkout = out["local"].date()
        due = cal.next_open(branch, checkout + timedelta(days=item["loan_days"]))
        renewed = 0
        returned = None
        for e in sorted(loan["later"], key=lambda e: (e["local"], e["event"])):
            d = e["local"].date()
            if e["type"] == "return":
                returned = d - timedelta(days=1) if e["via"] == "dropbox" else d
                break
            if d > policy.end or d > due or renewed >= item["renewals"]:
                continue
            renewed += 1
            due = cal.next_open(branch, d + timedelta(days=item["loan_days"]))
        if returned is not None and returned < policy.start:
            continue
        end = returned if returned is not None and returned <= policy.end else policy.end
        overdue = 0
        d = due + timedelta(days=1)
        while d <= end:
            overdue += cal.is_open(branch, d)
            d += timedelta(days=1)
        if overdue == 0:
            continue
        charged = 0 if overdue <= item["grace_days"] else overdue
        key = patron_key(out["patron"])
        cat = policy.categories[category_on(patrons[key], checkout)]
        base = 0 if out["item_type"] in cat["exempt"] else charged * item["daily"]
        assessed = half_up(min(base, item["loan_cap"]) * (100 - cat["discount"]), 100)
        mine = [w for w in waivers if w[0] == key and w[1] in (loan_id, "*")]
        if any(w[2] is None for w in mine):
            waived = assessed
        else:
            waived = min(assessed, sum(w[2] for w in mine))
        entries.setdefault(key, []).append({
            "loan": loan_id,
            "item": out["item"],
            "item_type": out["item_type"],
            "branch": branch,
            "checkout": checkout.isoformat(),
            "due": due.isoformat(),
            "returned": returned.isoformat() if returned is not None and returned <= policy.end else None,
            "overdue_days": overdue,
            "charged_days": charged,
            "assessed": assessed,
            "waived": waived,
            "capped": 0,
            "billed": assessed - waived,
        })

    statements = []
    branches = {b: {"branch": b, "loans": 0, "charged_days": 0, "assessed": 0, "waived": 0, "capped": 0, "billed": 0}
                for b in cal.order}
    for key in sorted(entries):
        rows = entries[key]
        category = category_on(patrons[key], policy.end)
        cap = policy.categories[category]["cap"]
        total = sum(r["billed"] for r in rows)
        if cap is not None and total > cap:
            left = total - cap
            for r in sorted(rows, key=lambda r: (r["due"], r["loan"]), reverse=True):
                take = min(left, r["billed"])
                r["capped"] = take
                r["billed"] -= take
                left -= take
        rows.sort(key=lambda r: (r["due"], r["loan"]))
        st = {"patron": shown[key], "category": category, "loans": rows}
        for k in ("assessed", "waived", "capped", "billed"):
            st[k] = sum(r[k] for r in rows)
        statements.append(st)
        for r in rows:
            b = branches[r["branch"]]
            b["loans"] += 1
            for k in ("charged_days", "assessed", "waived", "capped", "billed"):
                b[k] += r[k]

    result = {
        "library": policy.library,
        "period": {"start": policy.start.isoformat(), "end": policy.end.isoformat()},
        "statements": statements,
        "branches": [branches[b] for b in cal.order],
    }
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    Path(dst).write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
