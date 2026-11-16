"""Checks /app/out/statements.json against the approved statements for the period in /app/data.

Runs /app/bin/fees.py on /app/data and on a copy of it in another directory,
then reports how many statements and branch rows agree with the approved ones
and names up to three that do not. The approved statements are stored only
as salted digests, so the check cannot say what a statement should hold, only
whether it does.
"""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path("/app/bin/fees.py")
DATA = Path("/app/data")
OUTPUT = Path("/app/out/statements.json")
DIGESTS = Path(__file__).with_name("approved.json")
TOP_KEYS = {"library", "period", "statements", "branches"}
STATEMENT_KEYS = {"patron", "category", "loans", "assessed", "waived", "capped", "billed"}
LOAN_KEYS = {"loan", "item", "item_type", "branch", "checkout", "due", "returned", "overdue_days", "charged_days",
             "assessed", "waived", "capped", "billed"}
BRANCH_KEYS = {"branch", "loans", "charged_days", "assessed", "waived", "capped", "billed"}
AMOUNTS = ("assessed", "waived", "capped", "billed")


def digest(salt, value):
    return hashlib.sha256(f"{salt}|{json.dumps(value, sort_keys=True, ensure_ascii=False)}".encode()).hexdigest()


def is_count(v):
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def shape(got):
    if not isinstance(got, dict) or set(got) != TOP_KEYS:
        return f"the top level must be an object with exactly the keys {', '.join(sorted(TOP_KEYS))}"
    if not isinstance(got["statements"], list) or not isinstance(got["branches"], list):
        return "statements and branches must be lists"
    for i, s in enumerate(got["statements"]):
        if not isinstance(s, dict) or set(s) != STATEMENT_KEYS:
            return f"statements[{i}] must have exactly the keys {', '.join(sorted(STATEMENT_KEYS))}"
        if not isinstance(s["loans"], list) or not s["loans"]:
            return f"statements[{i}].loans must be a non-empty list"
        for j, loan in enumerate(s["loans"]):
            where = f"statements[{i}] ({s['patron']}) loans[{j}]"
            if not isinstance(loan, dict) or set(loan) != LOAN_KEYS:
                return f"{where} must have exactly the keys {', '.join(sorted(LOAN_KEYS))}"
            for k in ("overdue_days", "charged_days", *AMOUNTS):
                if not is_count(loan[k]):
                    return f"{where}.{k} must be a whole number"
            if loan["assessed"] - loan["waived"] - loan["capped"] != loan["billed"]:
                return f"{where}: assessed minus waived minus capped is not billed"
        for k in AMOUNTS:
            if s[k] != sum(loan[k] for loan in s["loans"]):
                return f"statements[{i}] ({s['patron']}).{k} is not the sum over its loans"
    for i, b in enumerate(got["branches"]):
        if not isinstance(b, dict) or set(b) != BRANCH_KEYS:
            return f"branches[{i}] must have exactly the keys {', '.join(sorted(BRANCH_KEYS))}"
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

    lines = []
    ok = digest(salt, [got["library"], got["period"]]) == approved["head"]
    if not ok:
        lines.append("  library or period differs")
    patrons = [s["patron"] for s in got["statements"]]
    if digest(salt, patrons) != approved["order"]:
        lines.append(f"  the list of statements differs: {len(patrons)} written, {approved['count']} approved")
        ok = False
    good = 0
    bad = []
    for s in got["statements"]:
        if approved["statements"].get(s["patron"]) == digest(salt, s):
            good += 1
        else:
            bad.append(s["patron"])
    lines.append(f"  statements matching the approved ones: {good} of {approved['count']}")
    branch_ok = 0
    for i, b in enumerate(got["branches"]):
        if i < len(approved["branches"]) and digest(salt, b) == approved["branches"][i]:
            branch_ok += 1
        else:
            bad.append(f"branch row {i + 1} ({b['branch']})")
    lines.append(f"  branch rows matching: {branch_ok} of {len(approved['branches'])}")
    for b in bad[:3]:
        lines.append(f"    differs: {b}")
    ok = ok and good == approved["count"] and branch_ok == len(approved["branches"]) == len(got["branches"]) and not bad
    return ok, lines


if __name__ == "__main__":
    ok, lines = check()
    print("OK: every statement and branch row matches the approved ones." if ok else "FAIL:")
    print("\n".join(lines))
    sys.exit(0 if ok else 1)
