"""Checks /app/out/summary.json against the reference figures for /app/data.

Reports how many values agree per section and names the first few that do not.
The reference figures are stored only as salted digests and are never printed.
"""
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path("/app/bin/summarize.py")
DATA = Path("/app/data")
SUMMARY = Path("/app/out/summary.json")
DIGESTS = Path(__file__).with_name("reference-digests.json")
SHOWN = 3
COUNTERS = ("corrections_applied", "handovers", "resends_dropped")


def is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def shape(got):
    if not isinstance(got, dict):
        return "the summary is not a JSON object"
    want = {"depots", "months", *COUNTERS}
    if set(got) != want:
        return f"top-level keys are {sorted(got)}, expected {sorted(want)}"
    for section in ("depots", "months"):
        if not isinstance(got[section], dict):
            return f"{section} must be an object"
        for key, v in got[section].items():
            if not isinstance(v, dict) or set(v) != {"shipments", "total_kg"}:
                return f"{section}.{key}: expected exactly the keys shipments and total_kg"
            if not is_int(v["shipments"]) or v["shipments"] < 0:
                return f"{section}.{key}.shipments must be a non-negative integer"
            if not is_num(v["total_kg"]) or v["total_kg"] < 0:
                return f"{section}.{key}.total_kg must be a non-negative number"
            if round(v["total_kg"], 2) != v["total_kg"]:
                return f"{section}.{key}.total_kg is not rounded to 2 decimals"
    for key in got["months"]:
        if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", key):
            return f"months key {key!r} is not YYYY-MM"
    if list(got["months"]) != sorted(got["months"]):
        return "months keys are not in ascending order"
    for key in COUNTERS:
        if not is_int(got[key]) or got[key] < 0:
            return f"{key} must be a non-negative integer"
    return None


def run(data_dir, out_file):
    try:
        p = subprocess.run([sys.executable, str(SCRIPT), str(data_dir), str(out_file)],
                           capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        return None, "the script did not finish within 600 seconds"
    if p.returncode != 0:
        tail = "\n".join(p.stderr.strip().splitlines()[-5:])
        return None, f"the script exited with status {p.returncode}:\n{tail}"
    try:
        return json.loads(Path(out_file).read_text()), None
    except (OSError, ValueError) as e:
        return None, f"the script did not write a JSON file to {out_file}: {e}"


def leaves(got):
    for section in ("depots", "months"):
        for key, v in got[section].items():
            yield section, f"{section}.{key}.shipments", str(v["shipments"])
            yield section, f"{section}.{key}.total_kg", f"{v['total_kg']:.2f}"
    for key in COUNTERS:
        yield "counters", key, str(got[key])


def compare(got):
    ref = json.loads(DIGESTS.read_text())
    salt = ref["salt"]
    agree = {s: 0 for s in ("depots", "months", "counters")}
    wrong = []
    for section, key, val in leaves(got):
        h = hashlib.sha256(f"{salt}|{key}|{val}".encode()).hexdigest()
        if h in ref[section]:
            agree[section] += 1
        else:
            wrong.append(key)
    lines = []
    for section in agree:
        lines.append(f"  {section}: {agree[section]} of {len(ref[section])} reference values matched")
    complete = not wrong and all(agree[s] == len(ref[s]) for s in agree)
    if wrong:
        lines.append(f"  values that disagree: {len(wrong)}; first {min(SHOWN, len(wrong))}: {', '.join(wrong[:SHOWN])}")
    return complete, lines


def check():
    if not SCRIPT.is_file():
        return False, [f"{SCRIPT} does not exist"]
    if not SUMMARY.is_file():
        return False, [f"{SUMMARY} does not exist"]
    try:
        got = json.loads(SUMMARY.read_text())
    except ValueError as e:
        return False, [f"{SUMMARY} is not valid JSON: {e}"]
    problem = shape(got)
    if problem:
        return False, [problem]
    with tempfile.TemporaryDirectory() as tmp:
        produced, err = run(DATA, Path(tmp) / "a.json")
        if err:
            return False, [err]
        if produced != got:
            return False, [f"{SUMMARY} differs from what the script writes for {DATA}"]
        copy = Path(tmp) / "copy"
        shutil.copytree(DATA, copy)
        again, err = run(copy, Path(tmp) / "b.json")
        if err:
            return False, [f"on a copy of {DATA} in another directory, {err}"]
        if again != got:
            return False, [f"the script gives a different result for a copy of {DATA} in another directory"]
    return compare(got)


if __name__ == "__main__":
    ok, lines = check()
    if ok:
        print("OK: every value matches the reference figures for /app/data.")
        sys.exit(0)
    print("FAIL:")
    print("\n".join(lines))
    sys.exit(1)
