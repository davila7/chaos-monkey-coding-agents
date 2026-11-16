"""Edits that turn the package sources under src/ into the tree shipped in /app.

Each entry is (id, cause class, file under quayside/, text in src, text
shipped). The B entries are shipped in 4.2.0. D1 is the defect of release
4.1.3 that 4.2.0 fixed: build.py applies it, without the B entries, to the
runs before the 4.2.0 deploy.

ACCEPT gives, per shipped defect, the file and the markers of the lines a
report may name.
"""

from pathlib import Path

BUGS = [
    ("B1", "retry-budget", "retry.py",
     '    if outcome == "throttled":\n'
     '        return ("retry", now + retry_after_ms)\n'
     '    msg["failures"] += 1\n'
     '    if msg["failures"] >= job.max_attempts:\n'
     '        return ("dead", "attempts-exhausted")\n',
     '    msg["failures"] += 1\n'
     '    if msg["failures"] >= job.max_attempts:\n'
     '        return ("dead", "attempts-exhausted")\n'
     '    if outcome == "throttled":\n'
     '        return ("retry", now + retry_after_ms)\n'),
    ("B2", "idempotency", "dedupe.py",
     '    field = "idem" if payload["v"] >= 3 else "idem_key"\n',
     '    field = "idem_key"\n'),
    ("B3", "visibility", "lease.py",
     "    return job.visibility_ms // 3\n",
     "    return cfg.visibility_ms // 3\n"),
    ("B4", "schema", "schema.py",
     '            return f"missing {name}"\n'
     "    return None\n",
     '            return f"missing {name}"\n'
     '    known = set(REQUIRED[job_type]) | {"v", "sent_at", "idem", "idem_key"}\n'
     "    extra = sorted(set(payload) - known)\n"
     "    if extra:\n"
     '        return f"unknown field {extra[0]}"\n'
     "    return None\n"),
    ("D1", "backoff", "retry.py",
     "    delay = job.backoff_ms\n"
     "    for _ in range(failures - 1):\n"
     "        delay *= 2\n"
     "        if delay >= job.backoff_max_ms:\n"
     "            return job.backoff_max_ms\n"
     "    return min(delay, job.backoff_max_ms)\n",
     "    return min(job.backoff_ms, job.backoff_max_ms)\n"),
]

SHIPPED = ("B1", "B2", "B3", "B4")
OLD = ("D1",)

ACCEPT = {
    "B1": ("retry.py", ['msg["failures"] += 1', 'if outcome == "throttled":']),
    "B2": ("dedupe.py", ['field = "idem_key"']),
    "B3": ("lease.py", ["return cfg.visibility_ms // 3"]),
    "B4": ("schema.py", ["known = set(REQUIRED[job_type])", "extra = sorted(set(payload) - known)", "if extra:"]),
}


def apply(pkg: Path, ids) -> None:
    for bug_id, _, rel, old, new in BUGS:
        if bug_id not in ids:
            continue
        p = pkg / rel
        text = p.read_text(encoding="utf-8")
        if text.count(old) != 1:
            raise SystemExit(f"{bug_id}: {rel}: expected one match of {old!r}")
        p.write_text(text.replace(old, new, 1), encoding="utf-8")


def accepted_lines(pkg: Path, bug_id: str) -> list[int]:
    rel, markers = ACCEPT[bug_id]
    lines = (pkg / rel).read_text(encoding="utf-8").splitlines()
    hits = [i + 1 for i, line in enumerate(lines) if any(m in line for m in markers)]
    if len(hits) != len(markers):
        raise SystemExit(f"{bug_id}: markers match lines {hits}")
    return hits
