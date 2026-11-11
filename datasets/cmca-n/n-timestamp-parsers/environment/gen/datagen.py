"""Seeded site folders: site.json and the six exports deskstats reads.

`write_site(folder, seed, name, offset, first, days)` writes one folder. The
values stay clear of the shapes on which the sources disagree (see
build.py); callers add such rows themselves.
"""

from __future__ import annotations

import csv
import json
import random
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

UTC = timezone.utc
QUEUES = ["billing", "tech", "sales", "access"]
AGENTS = ["ana", "ben", "chen", "dara", "eli", "femi"]
SHIFTS = [("07:00", "15:00"), ("08:30", "17:00"), ("14:00", "22:30"), ("22:00", "06:00"), ("06:30", "14:30"), ("16:00", "24:00")]


def tz_of(offset: str) -> timezone:
    sign = -1 if offset[0] == "-" else 1
    return timezone(sign * timedelta(hours=int(offset[1:3]), minutes=int(offset[4:6])))


def local_time(rng: random.Random, tz: timezone, first: date, days: int, lo: int = 7, hi: int = 20) -> datetime:
    d = first + timedelta(days=rng.randrange(days))
    return datetime(d.year, d.month, d.day, rng.randint(lo, hi), rng.randint(0, 59), rng.randint(0, 59), tzinfo=tz)


def ticket_text(rng: random.Random, t: datetime, tz: timezone) -> str:
    frac = f".{rng.randint(1, 999):03d}" if rng.random() < 0.3 else ""
    t = t.replace(microsecond=int(frac[1:]) * 1000 if frac else 0)
    kind = rng.random()
    if kind < 0.5:
        return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S") + frac + "Z"
    if kind < 0.75:
        return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S") + frac + "+00:00"
    return t.astimezone(tz).isoformat(timespec="milliseconds" if frac else "seconds")


def epoch_text(rng: random.Random, t: datetime) -> str:
    whole = int(t.timestamp())
    digits = rng.choice([0, 0, 1, 2, 3])
    if digits == 0:
        return str(whole)
    frac = str(rng.randrange(10**digits)).rjust(digits, "0")
    return f"{whole}.{frac}"


def chat_ms(rng: random.Random, t: datetime) -> int:
    ms = rng.randrange(1000)
    if ms == 500:
        ms = 499
    return int(t.timestamp()) * 1000 + ms


def write_site(folder: Path, seed: int, name: str, offset: str, first: date, days: int, *, bad_ticket: bool = True, tickets: int = 30, calls: int = 45, chats: int = 28) -> dict:
    rng = random.Random(seed)
    tz = tz_of(offset)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "site.json").write_text(json.dumps({"name": name, "utc_offset": offset}, indent=2) + "\n", encoding="utf-8")

    ticket_list = []
    rows = []
    for i in range(tickets):
        opened = local_time(rng, tz, first, days)
        closed = None if rng.random() < 0.15 else opened + timedelta(minutes=rng.randint(5, 2000), seconds=rng.randint(0, 59))
        tid = f"T-{seed % 1000:03d}{i:02d}"
        q = rng.choice(QUEUES)
        rows.append([tid, q, ticket_text(rng, opened, tz), ticket_text(rng, closed, tz) if closed else ""])
        ticket_list.append((tid, opened))
    if bad_ticket:
        rows.insert(rng.randrange(len(rows)), [f"T-{seed % 1000:03d}99", "tech", "pending", ""])
    with (folder / "tickets.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["id", "queue", "opened", "closed"])
        w.writerows(rows)

    esc = []
    sheet_left = 2
    for tid, opened in ticket_list:
        if rng.random() < 0.35:
            at = (opened + timedelta(minutes=rng.randint(3, 120))).astimezone(tz)
            if sheet_left and rng.random() < 0.3:
                text = at.strftime("%d.%m.%Y %H:%M")
                sheet_left -= 1
            else:
                text = at.strftime("%Y-%m-%d %H:%M")
            esc.append([tid, text, rng.choice(["tier2", "billing-lead", "network"])])
    with (folder / "escalations.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["ticket", "at", "to"])
        w.writerows(esc)

    lines = ["# epoch queue seconds"]
    for _ in range(calls):
        t = local_time(rng, tz, first, days, 6, 21)
        lines.append(f"{epoch_text(rng, t)} {rng.choice(QUEUES)} {rng.randint(20, 1500)}")
    (folder / "calls.log").write_text("\n".join(lines) + "\n", encoding="utf-8")

    out = []
    for i in range(chats):
        t = local_time(rng, tz, first, days, 7, 21)
        start = chat_ms(rng, t)
        end = start + rng.randint(60, 1800) * 1000 + rng.randint(-400, 400)
        if end % 1000 == 500:
            end += 1
        out.append(json.dumps({"id": f"C-{seed % 1000:03d}{i:02d}", "queue": rng.choice(QUEUES), "start_ms": start, "end_ms": end}))
    (folder / "chats.jsonl").write_text("\n".join(out) + "\n", encoding="utf-8")

    lines = ["# agent day shift"]
    for k in range(days):
        d = first + timedelta(days=k)
        for agent in sorted(rng.sample(AGENTS, rng.randint(2, 3))):
            a, b = rng.choice(SHIFTS)
            lines.append(f"{agent} {d.strftime('%d/%m/%y')} {a}-{b}")
    (folder / "roster.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    c1, c2 = first + timedelta(days=rng.randrange(days)), first + timedelta(days=rng.randrange(days))
    closures = ["# facilities calendar", f"{c1.isoformat()} staff training", f"{c2.strftime('%m/%d/%Y')} building maintenance"]
    (folder / "closures.txt").write_text("\n".join(closures) + "\n", encoding="utf-8")
    return {"folder": folder, "tz": tz, "first": first, "days": days}
