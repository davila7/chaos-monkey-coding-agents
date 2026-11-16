"""Checks /app/out/tables.json against the approved tables for the survey in /app/data.

Runs /app/bin/crosstabs.py on /app/data and on a copy of it in another
directory, then reports which summary figures agree with the approved ones
and, per table, how many entries (bases, weighted bases and values) agree,
naming up to three that do not. The approved figures are stored only as
salted digests, so the check cannot say what a figure should be, only whether
it is the same count, or within 0.01 of the number (docs/output.md 4.2).
"""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path("/app/bin/crosstabs.py")
DATA = Path("/app/data")
OUTPUT = Path("/app/out/tables.json")
DIGESTS = Path(__file__).with_name("approved-tables.json")
COUNTS = ("rows", "duplicates", "short_partials", "speeders", "complete", "partial")


def digest(salt, key, text):
    return hashlib.sha256(f"{salt}|{key}|{text}".encode()).hexdigest()[:24]


def candidates(v, count):
    if v is None:
        return ["null"]
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return []
    if count:
        return [str(v)] if isinstance(v, int) else []
    base = round(v, 2)
    return [f"{round(base + d, 2) + 0.0:.2f}" for d in (0.0, 0.01, -0.01)]


def matches(approved, key, v, count=False):
    want = approved["entries"].get(key)
    return want is not None and any(digest(approved["salt"], key, c) == want for c in candidates(v, count))


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


def shape(got):
    if not isinstance(got, dict) or set(got) != {"survey", "summary", "tables"}:
        return "the top level must be an object with exactly the keys survey, summary and tables"
    s = got["summary"]
    if not isinstance(s, dict) or set(s) != {"versions", "respondents", "effective_n", "weight_min", "weight_max"}:
        return "summary must have exactly the keys versions, respondents, effective_n, weight_min, weight_max"
    if not isinstance(s["versions"], list):
        return "summary.versions must be a list"
    for i, v in enumerate(s["versions"]):
        if not isinstance(v, dict) or set(v) != {"version", *COUNTS}:
            return f"summary.versions[{i}] must have exactly the keys version, {', '.join(COUNTS)}"
    if not isinstance(got["tables"], list):
        return "tables must be a list"
    for i, t in enumerate(got["tables"]):
        if not isinstance(t, dict) or set(t) != {"table", "columns"} or not isinstance(t["columns"], list):
            return f"tables[{i}] must have exactly the keys table and columns, columns a list"
        for j, c in enumerate(t["columns"]):
            if not isinstance(c, dict) or set(c) != {"column", "base", "weighted_base", "values"} \
                    or not isinstance(c["values"], dict):
                return f"tables[{i}].columns[{j}] must have exactly the keys column, base, weighted_base, values"
    return None


def check():
    approved = json.loads(DIGESTS.read_text(encoding="utf-8"))
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
    s = got["summary"]
    if [v["version"] for v in s["versions"]] != approved["versions"]:
        lines.append(f"  summary versions differ: {len(s['versions'])} written, {len(approved['versions'])} approved")
        ok = False
    bad = []
    for v in s["versions"]:
        for k in COUNTS:
            key = f"summary {v['version']} {k}"
            if not matches(approved, key, v[k], count=True):
                bad.append(key)
    if not matches(approved, "summary respondents", s["respondents"], count=True):
        bad.append("summary respondents")
    for k in ("effective_n", "weight_min", "weight_max"):
        if not matches(approved, f"summary {k}", s[k]):
            bad.append(f"summary {k}")
    lines.append("  summary: " + ("every figure matches" if not bad else "differs: " + ", ".join(bad)))
    ok = ok and not bad

    if [t["table"] for t in got["tables"]] != [t["table"] for t in approved["tables"]]:
        lines.append(f"  tables differ: {[t['table'] for t in got['tables']]} written")
        ok = False
    plan = {t["table"]: t for t in approved["tables"]}
    for t in got["tables"]:
        a = plan.get(t["table"])
        if a is None:
            continue
        if [c["column"] for c in t["columns"]] != a["columns"]:
            lines.append(f"  {t['table']}: column list differs ({len(t['columns'])} written, {len(a['columns'])} approved)")
            ok = False
        good, wrong = 0, []
        for c in t["columns"]:
            if c["column"] not in a["columns"]:
                continue
            if set(c["values"]) != set(a["rows"]):
                wrong.append(f"{c['column']} value keys")
            for key, v, count in [("base", c["base"], True), ("weighted_base", c["weighted_base"], False)] + \
                    [(r, c["values"].get(r), False) for r in a["rows"]]:
                name = f"{t['table']} {c['column']} {key}"
                if matches(approved, name, v, count):
                    good += 1
                else:
                    wrong.append(f"{c['column']} {key}")
        lines.append(f"  {t['table']}: {good} of {a['size']} approved entries match")
        for w in wrong[:3]:
            lines.append(f"    differs: {w}")
        ok = ok and not wrong and good == a["size"]
    return ok, lines


if __name__ == "__main__":
    ok, lines = check()
    print("OK: every figure matches the approved tables." if ok else "FAIL:")
    print("\n".join(lines))
    sys.exit(0 if ok else 1)
