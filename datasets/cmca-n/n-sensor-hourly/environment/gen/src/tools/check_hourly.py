"""Checks /app/out/hourly.json against the approved hourly values for the dumps in /app/data.

Runs /app/bin/hourly.py on /app/data and on a copy of it in another directory,
then reports, per quantity, how many hours agree with the approved values and
names up to three that do not. The approved values are stored only as salted
digests, so the check cannot say what a value should be, only whether it is
within 0.01 of it with the same n (docs/output.md 3.3).
"""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path("/app/bin/hourly.py")
DATA = Path("/app/data")
OUTPUT = Path("/app/out/hourly.json")
DIGESTS = Path(__file__).with_name("approved-hourly.json")
QUANTITIES = ("temp", "rh", "pres", "wspd", "wdir", "rain")
STATION_KEYS = {"station", "interval_s", "hours"}
HOUR_KEYS = {"hour", *QUANTITIES}


def digest(salt, key, n, text):
    return hashlib.sha256(f"{salt}|{key}|{n}|{text}".encode()).hexdigest()[:24]


def candidates(q, v):
    if v is None:
        return ["null"]
    base = round(v, 2)
    out = []
    for d in (0.0, 0.01, -0.01):
        x = round(base + d, 2)
        if q == "wdir":
            x = round(x % 360, 2)
            if x >= 360:
                x = 0.0
        out.append(f"{x + 0.0:.2f}")
    return out


def shape(got):
    if not isinstance(got, dict) or set(got) != {"stations"} or not isinstance(got["stations"], list):
        return "the top level must be an object with exactly the key stations, holding a list"
    for i, s in enumerate(got["stations"]):
        if not isinstance(s, dict) or set(s) != STATION_KEYS:
            return f"stations[{i}] must have exactly the keys {', '.join(sorted(STATION_KEYS))}"
        if not isinstance(s["hours"], list):
            return f"stations[{i}].hours must be a list"
        for j, h in enumerate(s["hours"]):
            where = f"stations[{i}] ({s['station']}) hours[{j}]"
            if not isinstance(h, dict) or set(h) != HOUR_KEYS:
                return f"{where} must have exactly the keys {', '.join(sorted(HOUR_KEYS))}"
            for q in QUANTITIES:
                e = h[q]
                if not isinstance(e, dict) or set(e) != {"value", "n"}:
                    return f"{where}.{q} must be an object with exactly the keys value and n"
                if not isinstance(e["n"], int) or isinstance(e["n"], bool):
                    return f"{where}.{q}.n must be a whole number"
                if e["value"] is not None and (isinstance(e["value"], bool) or
                                               not isinstance(e["value"], (int, float))):
                    return f"{where}.{q}.value must be a number or null"
    return None


def run(data, out):
    try:
        p = subprocess.run([sys.executable, str(SCRIPT), str(data), str(out)], capture_output=True, text=True,
                           timeout=600)
    except subprocess.TimeoutExpired:
        return None, "the script did not finish within 600 seconds"
    if p.returncode:
        tail = "\n".join(p.stderr.strip().splitlines()[-5:])
        return None, f"the script exited with status {p.returncode}:\n{tail}"
    try:
        return json.loads(Path(out).read_text(encoding="utf-8")), None
    except (OSError, ValueError) as e:
        return None, f"the script did not write JSON to {out}: {e}"


def check():
    approved = json.loads(DIGESTS.read_text(encoding="utf-8"))
    salt = approved["salt"]
    for p in (SCRIPT, OUTPUT):
        if not p.is_file():
            return False, [f"{p} does not exist"]
    try:
        got = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except ValueError as e:
        return False, [f"{OUTPUT} is not valid JSON: {e}"]
    problem = shape(got)
    if problem:
        return False, [problem]
    with tempfile.TemporaryDirectory() as tmp:
        produced, err = run(DATA, Path(tmp) / "a.json")
        if err:
            return False, [err]
        if produced != got:
            return False, [f"{OUTPUT} differs from what the script writes for {DATA}"]
        copy = Path(tmp) / "elsewhere"
        shutil.copytree(DATA, copy)
        again, err = run(copy, Path(tmp) / "b.json")
        if err:
            return False, [f"on a copy of {DATA}: {err}"]
        if again != got:
            return False, [f"the script gives a different result for a copy of {DATA} in another directory"]

    lines, ok = [], True
    want_ids = [s["station"] for s in approved["stations"]]
    have_ids = [s["station"] for s in got["stations"]]
    if have_ids != want_ids:
        lines.append(f"  stations differ: {len(have_ids)} written, {len(want_ids)} approved")
        ok = False
    want_by_id = {s["station"]: s for s in approved["stations"]}
    total = sum(len(s["hours"]) for s in approved["stations"])
    for s in got["stations"]:
        w = want_by_id.get(s["station"])
        if w is None:
            continue
        if s["interval_s"] != w["interval_s"]:
            lines.append(f"  {s['station']}: interval_s differs")
            ok = False
        hours = [h["hour"] for h in s["hours"]]
        if hours != w["hours"]:
            lines.append(f"  {s['station']}: hour list differs ({len(hours)} hours written, {len(w['hours'])} approved)")
            ok = False
    matching = {q: 0 for q in QUANTITIES}
    bad = []
    for s in got["stations"]:
        for h in s["hours"]:
            for q in QUANTITIES:
                key = f"{s['station']} {h['hour']} {q}"
                want = approved["values"].get(key)
                if want is None:
                    continue
                if any(digest(salt, key, h[q]["n"], c) == want for c in candidates(q, h[q]["value"])):
                    matching[q] += 1
                else:
                    bad.append(key)
    for q in QUANTITIES:
        lines.append(f"  {q}: {matching[q]} of {total} approved hours match")
        ok = ok and matching[q] == total
    for k in bad[:3]:
        lines.append(f"    differs: {k}")
    return ok, lines


if __name__ == "__main__":
    ok, lines = check()
    print("OK: every hourly value matches the approved values." if ok else "FAIL:")
    print("\n".join(lines))
    sys.exit(0 if ok else 1)
