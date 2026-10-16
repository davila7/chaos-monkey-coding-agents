"""Per-task validation without a model (SPEC 10.4 items 3 to 5).

    python -m cmca_harbor.validate --dataset datasets/cmca-s [--task s-followups]... \
        [--changed-since origin/main] --out results/task-validation/<run> [--jobs jobs] [--dry-run]

Runs Harbor's `oracle` under `clean` and `nop` under `clean` for every selected
task; on Track S the oracle also runs under every fault profile, since the
gateway applies the faults whatever the agent is. The oracle must score 1 and
`nop` 0. Writes `summary.json` in the format of `results/task-validation/` and
archives the evidence next to it. Exits 1 when a check fails.
"""

import argparse
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from cmca_harbor.common import REPO_ROOT
from cmca_harbor.trials import archive, plan, tasks

SEED = "task-validation"  # fixed, so a rerun of the same task draws the same faults
FAULT_PROFILES = ("light", "moderate", "heavy")
EXPECTED = {"oracle": 1.0, "nop": 0.0}


def changed_tasks(dataset: Path, base: str) -> list[str]:
    out = subprocess.run(["git", "diff", "--name-only", f"{base}...HEAD", "--", str(dataset)], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout
    rel = dataset.resolve().relative_to(REPO_ROOT)
    names = {Path(p).relative_to(rel).parts[0] for p in out.split()}
    return sorted(n for n in names if (dataset / n / "task.toml").exists())


def commands(dataset: Path, names: list[str], out: Path, jobs: Path) -> list[list[str]]:
    # Compose resolves a relative TT_CONFIG_DIR against the task directory, not the caller's.
    out, jobs = out.resolve(), jobs.resolve()
    track = "s" if dataset.name.endswith("-s") else "n"
    include = [arg for n in names for arg in ("-i", n)]
    runs: list[list[str]] = []
    if track == "s":
        for agent, profiles in (("oracle", ["clean", *FAULT_PROFILES]), ("nop", ["clean"])):
            for argv in plan(agent, SEED, dataset, profiles, 1, None, out / "configs" / agent, jobs, track="s"):
                runs.append(argv + include)
    else:
        # No injector runs on Track N for the built-in agents, so neither needs an engine config.
        for agent in ("oracle", "nop"):
            runs.append(["harbor", "run", "-p", str(dataset), "-a", agent, "-k", "1", "-o", str(jobs), "--job-name", f"{agent}-clean-a0", "-y", *include])
    return runs


def _events(trial: Path) -> list[dict[str, Any]]:
    for rel in ("artifacts/var/log/tt/events.jsonl", "agent/tt/events.jsonl"):
        p = trial / rel
        if p.exists():
            return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]
    return []


def collect(jobs: Path, job_names: list[str]) -> list[dict[str, Any]]:
    rows = []
    for job in job_names:
        for trial in sorted(p for p in (jobs / job).iterdir() if p.is_dir() and (p / "result.json").exists()):
            result = json.loads((trial / "result.json").read_text())
            rewards = (result.get("verifier_result") or {}).get("rewards") or {}
            events = _events(trial)
            rows.append({
                "job": job,
                "task": json.loads((trial / "config.json").read_text())["task"]["path"].rstrip("/").rsplit("/", 1)[-1],
                "reward": rewards.get("reward"),
                "calls": len(events),
                "eligible": sum(1 for e in events if e.get("decision") in ("pass", "apply")),
                "applied": dict(sorted(Counter(e["type"] for e in events if e.get("decision") == "apply").items())),
                "exception": (result.get("exception_info") or {}).get("exception_type"),
            })
    return sorted(rows, key=lambda r: (r["job"], r["task"]))


def failures(rows: list[dict[str, Any]], names: list[str], job_names: list[str]) -> list[str]:
    out = []
    seen = {(r["job"], r["task"]) for r in rows}
    out += [f"{job}/{n}: no trial" for job in job_names for n in names if (job, n) not in seen]
    for r in rows:
        want = EXPECTED[r["job"].split("-", 1)[0]]
        if r["reward"] != want:
            out.append(f"{r['job']}/{r['task']}: reward {r['reward']}, expected {want}" + (f" ({r['exception']})" if r["exception"] else ""))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="cmca_harbor.validate")
    ap.add_argument("--dataset", required=True, type=Path)
    ap.add_argument("--task", action="append", default=[])
    ap.add_argument("--changed-since", help="validate the tasks changed since this git ref")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--jobs", type=Path)
    ap.add_argument("--dry-run", action="store_true", help="print the Harbor commands only")
    args = ap.parse_args(argv)

    names = sorted(set(args.task) | set(changed_tasks(args.dataset, args.changed_since) if args.changed_since else []))
    if not args.task and not args.changed_since:
        names = [t.name for t in tasks(args.dataset)]
    if not names:
        print(f"{args.dataset}: no task to validate")
        return 0
    jobs = args.jobs or Path(tempfile.mkdtemp(prefix="cmca-validate-"))
    runs = commands(args.dataset, names, args.out, jobs)
    if args.dry_run:
        for argv_ in runs:
            print(" ".join(argv_))
        return 0
    for argv_ in runs:
        subprocess.run(argv_, cwd=REPO_ROOT, check=False)
    job_names = [argv_[argv_.index("--job-name") + 1] for argv_ in runs]
    rows = collect(jobs, job_names)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "summary.json").write_text(json.dumps(rows, indent=2) + "\n")
    for agent in EXPECTED:
        archive(agent, jobs, args.out)
    bad = failures(rows, names, job_names)
    for line in bad:
        print(f"FAIL {line}", file=sys.stderr)
    print(f"validated {len(names)} task(s) in {args.dataset}: {'ok' if not bad else f'{len(bad)} failure(s)'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
