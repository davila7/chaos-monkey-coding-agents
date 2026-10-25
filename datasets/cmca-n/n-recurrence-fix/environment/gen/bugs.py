"""Edits that turn the package sources under src/ into the tree shipped in /app.

Each entry is (id, file under agenda/, text in src, text shipped). The ids
group them: V entries fail the shipped unit tests, R entries pass them and
show in tools/check.py, X entries pass both and the visible data exercises
each on exactly one event (build.py checks it); held-out data exercises them
often.
"""

from pathlib import Path

BUGS = [
    ("V1", "rules/periods.py",
     "        elif n < 0 and -n <= len(all_days):\n            out.add(all_days[n])\n",
     "        elif n < 0 and -n <= len(all_days):\n            out.add(all_days[-n])\n"),
    ("V2", "rules/expand.py",
     "        return local.date() > value\n",
     "        return local.date() >= value\n"),
    ("V3", "zones.py",
     "        return local - timedelta(minutes=self.std)\n\n    def to_local",
     "        return local - timedelta(minutes=self.dst)\n\n    def to_local"),
    ("V4", "events/instances.py",
     "        generated = occurrences(event.rule, event.start, event.zone, horizon(event, window))\n",
     "        generated = (s for s in occurrences(event.rule, event.start, event.zone, horizon(event, window)) if s not in event.exdates)\n"),
    ("R1", "events/instances.py",
     "    return Instance(rid, start, start + timedelta(minutes=duration), o is not None)\n",
     "    return Instance(rid, start, event.zone.to_utc(local + timedelta(minutes=duration)), o is not None)\n"),
    ("R2", "events/instances.py",
     "    out.sort(key=lambda i: (i.start_utc, i.recurrence_id))\n",
     ""),
    ("R3", "events/instances.py",
     "    ids = {s for s in generated if s not in event.exdates}\n    ids.update(r for r in event.rdates if r not in event.exdates)\n",
     "    ids = [s for s in generated if s not in event.exdates]\n    ids.extend(r for r in event.rdates if r not in event.exdates)\n"),
    # The week of a two-weekly rule begins on Monday whatever WKST says.
    ("X1", "rules/periods.py",
     "        return week_start(start, rule.wkst) + timedelta(weeks=step)\n",
     "        return week_start(start, 0) + timedelta(weeks=step)\n"),
    # A UTC UNTIL is compared with the local digits of the generated time.
    ("X2", "rules/expand.py",
     "    return zone.to_utc(local) > value\n",
     "    return local > value\n"),
    # The expansion stops at the window, so an override cannot bring in an
    # instance whose recurrence id lies after it.
    ("X3", "events/instances.py",
     '    """The last local date the expansion has to reach: the window, or a later\n    original time that an override moves."""\n    last = window.last_local_day()\n    if event.overrides:\n        last = max(last, max(event.overrides).date())\n    return last\n',
     '    """The last local date the expansion has to reach."""\n    return window.last_local_day()\n'),
]


def apply(package_dir: Path, ids) -> None:
    """Applies the named bugs to a copy of the agenda package in place."""
    for bug_id, rel, good, bad in BUGS:
        if bug_id not in ids:
            continue
        p = Path(package_dir) / rel
        text = p.read_text(encoding="utf-8")
        if text.count(good) != 1:
            raise SystemExit(f"{bug_id} {rel}: expected one match")
        p.write_text(text.replace(good, bad, 1), encoding="utf-8")


ALL = sorted({b[0] for b in BUGS})
