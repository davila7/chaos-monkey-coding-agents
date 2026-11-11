"""Checks /app/out/tally.json against the certified results for the election in /app/data.

Runs /app/bin/tally.py on /app/data and on a copy of it in another directory,
then reports how many contests and rounds agree with the certified ones and
names up to three that do not. The certified results are stored only as
salted digests, so the check cannot say what a round should hold, only
whether it does.
"""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path("/app/bin/tally.py")
DATA = Path("/app/data")
OUTPUT = Path("/app/out/tally.json")
DIGESTS = Path(__file__).with_name("certified.json")
CONTEST_KEYS = {"contest", "ballots", "winner", "rounds"}
ROUND_KEYS = {"round", "tallies", "exhausted", "eliminated"}


def digest(salt, value):
    return hashlib.sha256(f"{salt}|{json.dumps(value, sort_keys=True, ensure_ascii=False)}".encode()).hexdigest()


def is_count(v):
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def shape(got):
    if not isinstance(got, dict) or set(got) != {"election", "contests"}:
        return "the top level must be an object with exactly the keys election and contests"
    if not isinstance(got["contests"], list):
        return "contests must be a list"
    for i, c in enumerate(got["contests"]):
        if not isinstance(c, dict) or set(c) != CONTEST_KEYS:
            return f"contests[{i}] must have exactly the keys {', '.join(sorted(CONTEST_KEYS))}"
        if not is_count(c["ballots"]):
            return f"contests[{i}].ballots must be a whole number"
        if c["winner"] is not None and not isinstance(c["winner"], str):
            return f"contests[{i}].winner must be a candidate id or null"
        if not isinstance(c["rounds"], list) or not c["rounds"]:
            return f"contests[{i}].rounds must be a non-empty list"
        for j, r in enumerate(c["rounds"]):
            where = f"contests[{i}] ({c['contest']}) rounds[{j}]"
            if not isinstance(r, dict) or set(r) != ROUND_KEYS:
                return f"{where} must have exactly the keys {', '.join(sorted(ROUND_KEYS))}"
            if r["round"] != j + 1:
                return f"{where}.round must be {j + 1}"
            if not isinstance(r["tallies"], dict) or not all(is_count(v) for v in r["tallies"].values()):
                return f"{where}.tallies must map candidate ids to whole numbers"
            if not is_count(r["exhausted"]):
                return f"{where}.exhausted must be a whole number"
            if not isinstance(r["eliminated"], list) or not all(isinstance(x, str) for x in r["eliminated"]):
                return f"{where}.eliminated must be a list of candidate ids"
            if sum(r["tallies"].values()) + r["exhausted"] != c["ballots"]:
                return f"{where}: the votes and exhausted ballots do not add up to ballots"
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
    certified = json.loads(DIGESTS.read_text(encoding="utf-8"))
    salt = certified["salt"]
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

    lines = []
    ok = got["election"] == certified["election"]
    if not ok:
        lines.append("  election differs")
    ids = [c["contest"] for c in got["contests"]]
    if ids != certified["order"]:
        lines.append(f"  contest list differs: {len(ids)} written, {len(certified['order'])} certified")
        ok = False
    bad = []
    rounds_ok = 0
    rounds_all = sum(len(v["rounds"]) for v in certified["contests"].values())
    contests_ok = 0
    for c in got["contests"]:
        want = certified["contests"].get(c["contest"])
        if want is None:
            continue
        head = {"ballots": c["ballots"], "winner": c["winner"], "rounds": len(c["rounds"])}
        good = digest(salt, [c["contest"], head]) == want["head"]
        for j, r in enumerate(c["rounds"]):
            if j < len(want["rounds"]) and digest(salt, [c["contest"], r]) == want["rounds"][j]:
                rounds_ok += 1
            else:
                good = False
                bad.append(f"{c['contest']} round {j + 1}")
        if not good and not any(b.startswith(f"{c['contest']} round") for b in bad):
            bad.append(f"{c['contest']} (ballots, winner or number of rounds)")
        contests_ok += good
    lines.append(f"  contests matching the certified results: {contests_ok} of {len(certified['order'])}")
    lines.append(f"  rounds matching: {rounds_ok} of {rounds_all}")
    for b in bad[:3]:
        lines.append(f"    differs: {b}")
    ok = ok and contests_ok == len(certified["order"]) and not bad
    return ok, lines


if __name__ == "__main__":
    ok, lines = check()
    print("OK: every contest matches the certified results." if ok else "FAIL:")
    print("\n".join(lines))
    sys.exit(0 if ok else 1)
