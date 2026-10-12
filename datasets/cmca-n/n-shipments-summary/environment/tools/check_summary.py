"""Checks the shape of /app/out/summary.json. Reports the first problem only; never checks values."""
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


def is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def shape(got, depots):
    if not isinstance(got, dict):
        return "summary is not a JSON object"
    if set(got) != {"depots", "by_month", "duplicates_resolved"}:
        return f"top-level keys are {sorted(got)}, expected by_month, depots, duplicates_resolved"
    if not isinstance(got["depots"], dict) or set(got["depots"]) != depots:
        found = sorted(got["depots"]) if isinstance(got["depots"], dict) else type(got["depots"]).__name__
        return f"depots are {found}, expected one per export: {sorted(depots)}"
    for name, d in got["depots"].items():
        if not isinstance(d, dict) or set(d) != {"shipments", "total_kg"}:
            return f"depot {name}: expected exactly the keys shipments and total_kg"
        if not is_int(d["shipments"]) or d["shipments"] < 0:
            return f"depot {name}: shipments must be a non-negative integer"
        kg = d["total_kg"]
        if isinstance(kg, bool) or not isinstance(kg, (int, float)) or kg < 0:
            return f"depot {name}: total_kg must be a non-negative number"
        if round(kg, 2) != kg:
            return f"depot {name}: total_kg is not rounded to 2 decimals"
        if (d["shipments"] == 0) != (kg == 0):
            return f"depot {name}: shipments and total_kg disagree about whether anything was counted"
    months = got["by_month"]
    if not isinstance(months, dict):
        return "by_month must be an object"
    for key, n in months.items():
        if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", key):
            return f"by_month key {key!r} is not YYYY-MM"
        if not is_int(n) or n <= 0:
            return f"by_month[{key}] must be a positive integer"
    if list(months) != sorted(months):
        return "by_month keys are not in ascending order"
    if sum(months.values()) != sum(d["shipments"] for d in got["depots"].values()):
        return "by_month does not add up to the total number of counted shipments"
    if not is_int(got["duplicates_resolved"]) or got["duplicates_resolved"] < 0:
        return "duplicates_resolved must be a non-negative integer"
    return None


def run(data_dir, out_file):
    try:
        p = subprocess.run([sys.executable, str(SCRIPT), str(data_dir), str(out_file)],
                           capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return None, "the script did not finish within 120 seconds"
    if p.returncode != 0:
        tail = "\n".join(p.stderr.strip().splitlines()[-5:])
        return None, f"the script exited with status {p.returncode}:\n{tail}"
    try:
        return json.loads(Path(out_file).read_text()), None
    except (OSError, ValueError) as e:
        return None, f"the script did not write a JSON file to {out_file}: {e}"


def check():
    if not SCRIPT.is_file():
        return f"{SCRIPT} does not exist"
    if not SUMMARY.is_file():
        return f"{SUMMARY} does not exist"
    try:
        got = json.loads(SUMMARY.read_text())
    except ValueError as e:
        return f"{SUMMARY} is not valid JSON: {e}"
    depots = {p.stem for p in DATA.iterdir() if p.is_file()}
    problem = shape(got, depots)
    if problem:
        return problem
    with tempfile.TemporaryDirectory() as tmp:
        produced, err = run(DATA, Path(tmp) / "a.json")
        if err:
            return err
        if produced != got:
            return f"{SUMMARY} differs from what the script writes for {DATA}"
        copy = Path(tmp) / "copy"
        shutil.copytree(DATA, copy)
        again, err = run(copy, Path(tmp) / "b.json")
        if err:
            return f"on a copy of {DATA} in another directory, {err}"
        if again != got:
            return f"the script gives a different result for a copy of {DATA} in another directory"
    return None


if __name__ == "__main__":
    problem = check()
    if problem:
        print(f"FAIL: {problem}")
        sys.exit(1)
    print("OK: the summary has the expected shape and matches the script output. Values are not checked.")
