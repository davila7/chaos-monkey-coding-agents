"""Counts the shapes on which the sources of n-timestamp-parsers disagree, in the visible samples and the held-out sites.

Usage: python3 shapes.py SAMPLES_DIR HELDOUT_DIR
SAMPLES_DIR is /app/samples of a fresh build; HELDOUT_DIR is the data folder
that tests/heldout.py writes (verify.py puts it under WORK/data).
"""

import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SHEET = ("%Y-%m-%d %H:%M", "%d.%m.%Y %H:%M")


def iso(text):
    try:
        return datetime.fromisoformat(text.strip())
    except ValueError:
        return None


def sheet(text):
    for layout in SHEET:
        try:
            return datetime.strptime(text.strip(), layout)
        except ValueError:
            pass
    return None


def count(root: Path) -> dict:
    c = dict.fromkeys([
        "sites", "offset_not_whole_hour", "ticket_no_offset", "ticket_basic_or_week_or_hour", "ticket_sheet_layout",
        "ticket_last_second_fraction", "sheet_fallback", "sheet_unpadded", "call_float_carries", "call_us_carries",
        "chat_ms_half", "roster_24_end", "roster_24_start", "roster_equal", "roster_4digit_or_unpadded", "closure_rejected", "closure_week_or_unpadded"], 0)
    for site in sorted(p for p in root.iterdir() if (p / "site.json").exists() and (p / "calls.log").exists()):
        c["sites"] += 1
        off = json.loads((site / "site.json").read_text()).get("utc_offset")
        if isinstance(off, str) and re.fullmatch(r"[+-]\d\d:(?!00)\d\d", off):
            c["offset_not_whole_hour"] += 1
        with (site / "tickets.csv").open(newline="") as f:
            for row in csv.DictReader(f):
                for v in (row["opened"], row["closed"]):
                    if not v.strip():
                        continue
                    t = iso(v)
                    if t is None:
                        c["ticket_sheet_layout"] += sheet(v) is not None
                        continue
                    c["ticket_no_offset"] += t.tzinfo is None
                    c["ticket_basic_or_week_or_hour"] += bool(re.match(r"\d{8}T|\d{4}-W|\d{4}-\d\d-\d\dT\d\dZ$", v))
                    c["ticket_last_second_fraction"] += (t.hour, t.minute, t.second) == (23, 59, 59) and t.microsecond > 0
        with (site / "escalations.csv").open(newline="") as f:
            for row in csv.DictReader(f):
                if iso(row["at"]) is None:
                    c["sheet_fallback"] += 1
                    c["sheet_unpadded"] += bool(re.search(r"(^|[-. ])\d([-. :]|$)", row["at"]))
        for line in (site / "calls.log").read_text().splitlines():
            if not line or line.startswith("#"):
                continue
            e = line.split()[0]
            whole = e.split(".")[0]
            if whole.isdigit():
                c["call_float_carries"] += int(float(e)) != int(whole)
                c["call_us_carries"] += datetime.fromtimestamp(float(e), timezone.utc).replace(microsecond=0) != datetime.fromtimestamp(int(float(e)), timezone.utc)
        for line in (site / "chats.jsonl").read_text().splitlines():
            if line.strip():
                raw = json.loads(line)
                for k in ("start_ms", "end_ms"):
                    if isinstance(raw.get(k), (int, float)) and raw[k] % 1000 == 500:
                        c["chat_ms_half"] += 1
        for line in (site / "roster.txt").read_text().splitlines():
            if not line or line.startswith("#"):
                continue
            _, day, span = line.split()
            a, b = span.split("-")
            c["roster_24_end"] += b == "24:00"
            c["roster_24_start"] += a == "24:00"
            c["roster_equal"] += a == b
            c["roster_4digit_or_unpadded"] += not re.fullmatch(r"\d\d/\d\d/\d\d", day) or not re.fullmatch(r"\d\d:\d\d-\d\d:\d\d", span)
        for line in (site / "closures.txt").read_text().splitlines():
            if not line or line.startswith("#"):
                continue
            d = line.split()[0]
            if "-" in d:
                ok = iso(d + "T00:00") is not None or bool(re.match(r"\d{4}-W", d))
            else:
                try:
                    datetime.strptime(d, "%m/%d/%Y")
                    ok = True
                except ValueError:
                    ok = False
            c["closure_rejected"] += not ok
            c["closure_week_or_unpadded"] += ok and bool(re.match(r"\d{4}-W|\d/|\d\d?/\d/", d))
    return c


if __name__ == "__main__":
    print("visible", count(Path(sys.argv[1])))
    print("held-out", count(Path(sys.argv[2])))
