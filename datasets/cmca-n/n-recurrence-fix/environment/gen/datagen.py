"""Writes a data directory for the agenda package: zones.json, agenda.json and
one file per event under events/.

The output depends only on the seed and the keyword arguments. The visible data
(build.py) and the held-out data (tests/verify.py) come from this one file.
"""

import json
import random
from datetime import date, datetime, timedelta
from pathlib import Path

DAYS = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")

# Every offset stays under 12 hours from UTC; generate() relies on it to keep
# UTC UNTIL values away from the instances of the visible data.
ZONES = {
    "Harbor Point": {"std_offset_min": 60, "dst": {"offset_min": 120,
        "start": {"month": 3, "week": "last", "weekday": "SU", "time": "01:00", "basis": "utc"},
        "end": {"month": 10, "week": "last", "weekday": "SU", "time": "01:00", "basis": "utc"}}},
    "Cedar Falls": {"std_offset_min": -300, "dst": {"offset_min": -240,
        "start": {"month": 3, "week": "2", "weekday": "SU", "time": "02:00"},
        "end": {"month": 11, "week": "1", "weekday": "SU", "time": "02:00"}}},
    "South Reach": {"std_offset_min": 600, "dst": {"offset_min": 660,
        "start": {"month": 10, "week": "1", "weekday": "SU", "time": "02:00"},
        "end": {"month": 4, "week": "1", "weekday": "SU", "time": "03:00"}}},
    "Kelp Isle": {"std_offset_min": 630, "dst": {"offset_min": 660,
        "start": {"month": 10, "week": "1", "weekday": "SU", "time": "02:00"},
        "end": {"month": 4, "week": "1", "weekday": "SU", "time": "02:00"}}},
    "Mesa Verde": {"std_offset_min": -420},
    "Lantern Bay": {"std_offset_min": 345},
    "Frost Hollow": {"std_offset_min": -210, "dst": {"offset_min": -150,
        "start": {"month": 3, "week": "2", "weekday": "SU", "time": "02:00"},
        "end": {"month": 11, "week": "1", "weekday": "SU", "time": "02:00"}}},
    "Pine Ridge": {"std_offset_min": 120, "dst": {"offset_min": 180,
        "start": {"month": 3, "week": "last", "weekday": "FR", "time": "02:00"},
        "end": {"month": 10, "week": "last", "weekday": "SU", "time": "02:00"}}},
    "Coral Steps": {"std_offset_min": -180, "dst": {"offset_min": -120,
        "start": {"month": 11, "week": "1", "weekday": "SU", "time": "00:00"},
        "end": {"month": 2, "week": "3", "weekday": "SU", "time": "00:00"}}},
    "Glass Harbor": {"std_offset_min": 0, "dst": {"offset_min": 60,
        "start": {"month": 3, "week": "last", "weekday": "SU", "time": "01:00", "basis": "utc"},
        "end": {"month": 10, "week": "last", "weekday": "SU", "time": "01:00", "basis": "utc"}}},
}
HELD_OUT_ZONES = {
    "Ash Fjord": {"std_offset_min": -540, "dst": {"offset_min": -480,
        "start": {"month": 3, "week": "2", "weekday": "SU", "time": "02:00"},
        "end": {"month": 11, "week": "1", "weekday": "SU", "time": "02:00"}}},
    "Tern Atoll": {"std_offset_min": 690, "dst": {"offset_min": 750,
        "start": {"month": 9, "week": "last", "weekday": "SU", "time": "02:00"},
        "end": {"month": 4, "week": "1", "weekday": "SU", "time": "03:00"}}},
    "Ochre Plain": {"std_offset_min": 570, "dst": {"offset_min": 630,
        "start": {"month": 10, "week": "1", "weekday": "SU", "time": "16:00", "basis": "utc"},
        "end": {"month": 4, "week": "1", "weekday": "SU", "time": "16:00", "basis": "utc"}}},
}
FIXED = ("Mesa Verde", "Lantern Bay")

SUMMARIES = ("Standup", "Planning", "Review", "Office hours", "Night shift", "Retreat", "Payroll run",
             "Board call", "Maintenance", "Training", "On-call handover", "Inventory count", "Release window")


def _day_step(freq: str) -> int:
    return {"DAILY": 1, "WEEKLY": 7}[freq]


class Gen:
    def __init__(self, seed: int, window: tuple[date, date], held_out: bool):
        self.r = random.Random(seed)
        # Choices added after the first release draw from their own generator,
        # so the older choices of a seed keep their values.
        self.r2 = random.Random(seed * 7 + 3)
        self.window = window
        self.held_out = held_out
        self.zone_names = list(ZONES) + (list(HELD_OUT_ZONES) if held_out else [])

    def start(self) -> datetime:
        r = self.r
        lo, hi = self.window
        d = lo - timedelta(days=150) + timedelta(days=r.randrange((hi - lo).days + 120))
        hour = r.choice((0, 1, 1, 2, 2, 2, 3, 6, 8, 9, 10, 13, 17, 20, 22, 23))
        return datetime(d.year, d.month, d.day, hour, r.choice((0, 0, 15, 30, 45)))

    def duration(self) -> int:
        r = self.r
        kind = r.random()
        if kind < 0.6:
            return r.choice((15, 30, 45, 60, 90))
        if kind < 0.85:
            return r.choice((240, 480, 600, 720))
        return r.choice((1440, 2160, 2880))

    def rule(self, start: datetime) -> tuple[str | None, str | None, int]:
        """(rrule, simple frequency, step) where the simple frequency names a
        rule whose times are start + k x step, or None."""
        r = self.r
        fam = r.choice(("none", "daily", "daily", "weekly", "weekly", "weekly-days", "monthly-day", "monthly-pos", "monthly-setpos", "yearly"))
        parts, simple, step = [], None, 0
        if fam == "none":
            return None, None, 0
        if fam == "daily":
            interval = r.choice((1, 1, 2, 3))
            parts = ["FREQ=DAILY"] + ([f"INTERVAL={interval}"] if interval > 1 else [])
            if r.random() < 0.25:
                parts.append("BYDAY=MO,TU,WE,TH,FR")
            else:
                simple, step = "days", interval
        elif fam == "weekly":
            interval = r.choice((1, 1, 2))
            parts = ["FREQ=WEEKLY"] + ([f"INTERVAL={interval}"] if interval > 1 else [])
            simple, step = "days", 7 * interval
        elif fam == "weekly-days":
            interval = r.choice((1, 1, 2, 3))
            days = sorted(r.sample(range(7), r.choice((2, 2, 3))))
            parts = ["FREQ=WEEKLY", f"BYDAY={','.join(DAYS[d] for d in days)}"]
            if interval > 1:
                parts.append(f"INTERVAL={interval}")
            if interval > 1 and (self.held_out and self.r2.random() < 0.6):
                parts.append(f"WKST={self.r2.choice(('SU', 'SA', 'WE', 'TH'))}")
            elif interval == 1 and r.random() < 0.3:
                parts.append(f"WKST={r.choice(('SU', 'SA'))}")
        elif fam == "monthly-day":
            day = r.choice((1, 5, 15, 28, 29, 30, 31, -1, -2))
            interval = r.choice((1, 1, 2, 3))
            parts = ["FREQ=MONTHLY", f"BYMONTHDAY={day}"] + ([f"INTERVAL={interval}"] if interval > 1 else [])
            if 1 <= day <= 28:
                simple, step = f"months:{day}", interval
        elif fam == "monthly-pos":
            n = r.choice(("1", "2", "3", "4", "-1", "-2", "5"))
            parts = ["FREQ=MONTHLY", f"BYDAY={n}{r.choice(DAYS)}"]
        elif fam == "monthly-setpos":
            pos = r.choice(("1", "-1", "2", "-2"))
            days = r.choice(("MO,TU,WE,TH,FR", "SA,SU", "MO,WE,FR"))
            parts = ["FREQ=MONTHLY", f"BYDAY={days}", f"BYSETPOS={pos}"]
        else:
            if r.random() < 0.5:
                months = sorted(r.sample(range(1, 13), r.choice((1, 2))))
                parts = ["FREQ=YEARLY", f"BYMONTH={','.join(map(str, months))}", f"BYDAY={r.choice(('1', '2', '-1', '4'))}{r.choice(DAYS)}"]
            else:
                parts = ["FREQ=YEARLY", f"BYMONTH={r.choice((2, 2, 4, 6, 9))}", f"BYMONTHDAY={r.choice((28, 29, 30, 31, -1))}"]
        end = r.random()
        if end < 0.35:
            parts.append(f"COUNT={r.randint(2, 40)}")
        elif end < 0.55:
            u = start.date() + timedelta(days=r.randint(20, 500))
            parts.append(f"UNTIL={u:%Y%m%d}")
        elif end < 0.7:
            u = start.date() + timedelta(days=r.randint(20, 500))
            if self.held_out:
                t = start + timedelta(minutes=self.r2.randint(-720, 720))
                parts.append(f"UNTIL={u:%Y%m%d}T{t:%H%M}00Z")
            else:
                t = start + timedelta(hours=12)
                parts.append(f"UNTIL={u:%Y%m%d}T{t:%H%M}00Z")
        r.shuffle(parts)
        return ";".join(parts), simple, step

    def times(self, start: datetime, simple: str | None, step: int, count: int | None, n: int) -> list[datetime]:
        if simple is None:
            return []
        out = []
        for k in range(1, n):
            if count is not None and k >= count:
                break
            if simple == "days":
                out.append(start + timedelta(days=k * step))
            else:
                # Monthly on a day from 1 to 28: the first time after the start
                # is in the start month or the next one.
                day = int(simple.split(":")[1])
                first = start.year * 12 + start.month - 1 + (day <= start.day)
                i = first + (k - 1) * step
                out.append(start.replace(year=i // 12, month=i % 12 + 1, day=day))
        return out


def _count(rule: str | None) -> int | None:
    for part in (rule or "").split(";"):
        if part.startswith("COUNT="):
            return int(part[6:])
    return None


def _local(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M")


BROKEN = (
    ("rrule", "FREQ=WEEKLY;COUNT=5;UNTIL=20280101"),
    ("rrule", "FREQ=WEEKLY;BYDAY=2MO"),
    ("rrule", "FREQ=DAILY;BYHOUR=9"),
    ("rrule", "FREQ=YEARLY;BYDAY=-1SU"),
    ("rrule", "FREQ=WEEKLY;BYSETPOS=1;BYDAY=MO,TU"),
    ("rrule", "FREQ=MONTHLY;BYMONTHDAY=0"),
    ("rrule", "FREQ=MONTHLY;BYDAY=6FR"),
    ("zone", "Atlantis"),
    ("duration_min", 0),
    ("overrides", [{"recurrence_id": "2027-05-01T09:00"}]),
    ("overrides", [{"recurrence_id": "2027-05-01T09:00", "cancelled": True, "start": "2027-05-02T09:00"}]),
    ("start", "2027-02-30T09:00"),
)


def generate(out, seed: int, events: int = 170, held_out: bool = False) -> None:
    out = Path(out)
    (out / "events").mkdir(parents=True, exist_ok=True)
    window = (date(2027, 1, 1), date(2028, 7, 1)) if not held_out else (date(2027, 2, 15), date(2029, 1, 1))
    zones = dict(ZONES)
    if held_out:
        zones.update(HELD_OUT_ZONES)
    (out / "zones.json").write_text(json.dumps(zones, indent=2) + "\n", encoding="utf-8")
    (out / "agenda.json").write_text(json.dumps({"from": f"{window[0]}", "to": f"{window[1]}"}) + "\n", encoding="utf-8")
    g = Gen(seed, window, held_out)
    r = g.r
    end_day = datetime.combine(window[1], datetime.min.time())
    for i in range(events):
        uid = f"EV-{1000 + i}"
        start = g.start()
        rule, simple, step = g.rule(start)
        ev = {"uid": uid, "summary": r.choice(SUMMARIES), "zone": r.choice(g.zone_names), "start": _local(start),
              "duration_min": g.duration()}
        if rule:
            ev["rrule"] = rule
        later = [t for t in g.times(start, simple, step, _count(rule), 60) if "UNTIL" not in (rule or "") or t.date() <= start.date() + timedelta(days=20)]
        if later and r.random() < 0.35:
            ev["exdate"] = [_local(t) for t in r.sample(later, min(len(later), r.randint(1, 3)))]
            if r.random() < 0.3:
                ev["exdate"].append(_local(start))
        if r.random() < 0.3:
            extra = []
            for _ in range(r.randint(1, 2)):
                if later and r.random() < 0.5:
                    extra.append(_local(r.choice(later)))
                else:
                    extra.append(_local(start + timedelta(days=r.randint(-40, 300), hours=r.choice((0, 0, 1, -1)))))
            ev["rdate"] = extra
        targets = [t for t in later if t < end_day - timedelta(days=2)]
        if targets and r.random() < 0.4:
            overrides = []
            for t in r.sample(targets, min(len(targets), r.randint(1, 3))):
                kind = r.random()
                if kind < 0.25:
                    overrides.append({"recurrence_id": _local(t), "cancelled": True})
                elif kind < 0.75:
                    moved = t + timedelta(minutes=r.choice((-1440, -90, -60, 30, 120, 1440, 2 * 1440 + 60, 9 * 1440)))
                    overrides.append({"recurrence_id": _local(t), "start": _local(moved)})
                elif kind < 0.9:
                    overrides.append({"recurrence_id": _local(t), "duration_min": r.choice((20, 75, 300))})
                else:
                    overrides.append({"recurrence_id": _local(t), "start": _local(t + timedelta(hours=3)), "duration_min": 45})
            if r.random() < 0.15:
                overrides.append({"recurrence_id": _local(start + timedelta(minutes=7)), "cancelled": True})
            ev["overrides"] = overrides
        if held_out and simple == "days" and _count(rule) is None and "UNTIL" not in (rule or "") and g.r2.random() < 0.4:
            far = start + timedelta(days=step * ((end_day - start).days // step + g.r2.randint(1, 30)))
            moved = end_day - timedelta(days=g.r2.randint(1, 60), hours=g.r2.randint(0, 12))
            ev.setdefault("overrides", []).append({"recurrence_id": _local(far), "start": _local(moved)})
        if r.random() < 0.06:
            key, value = r.choice(BROKEN)
            ev[key] = value
        (out / "events" / f"{uid}.json").write_text(json.dumps(ev, indent=2) + "\n", encoding="utf-8")
    if not held_out:
        _triggers(out, events)


def _triggers(out: Path, n: int) -> None:
    """One event of the visible data for each case that the generated events
    leave out: a two-weekly rule with WKST on Sunday, a UTC UNTIL that falls
    between the local and the UTC digits of an instance, and an override that
    moves an instance from after the window into it."""
    fixed = [
        {"uid": f"EV-{1000 + n}", "summary": "Team rota", "zone": "Pine Ridge", "start": "2027-04-06T10:00",
         "duration_min": 60, "rrule": "FREQ=WEEKLY;INTERVAL=2;COUNT=8;BYDAY=TU,SU;WKST=SU"},
        {"uid": f"EV-{1001 + n}", "summary": "Market open", "zone": "Lantern Bay", "start": "2027-09-01T08:00",
         "duration_min": 30, "rrule": "FREQ=DAILY;UNTIL=20270910T050000Z"},
        {"uid": f"EV-{1002 + n}", "summary": "Audit", "zone": "Mesa Verde", "start": "2027-11-03T09:00",
         "duration_min": 90, "rrule": "FREQ=WEEKLY",
         "overrides": [{"recurrence_id": "2028-08-16T09:00", "start": "2028-06-20T09:00"}]},
    ]
    for ev in fixed:
        (out / "events" / f"{ev['uid']}.json").write_text(json.dumps(ev, indent=2) + "\n", encoding="utf-8")
