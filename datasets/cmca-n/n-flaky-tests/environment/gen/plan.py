"""Authoring tool, not run by the image build: draws the CI runs that the logs
show and works out which defect each logged failure comes from.

Usage: python3 plan.py RUNS_JSON TRUTH_JSON

For every candidate run it runs the suite with the parameters of the run on
the correct package, on the shipped package, and on the correct package with
one edit of bugs.py at a time. A run is kept only when the correct package
passes, every failure of the shipped package fails with exactly one single
edit, and no single edit fails a test the shipped package passes, so each
logged failure has one cause. TRUTH_JSON gets, per shipped edit, its class,
file, the lines a report may name and the tests the kept runs show failing
because of it. Run it in the task image (Python 3.12) so the logs match.
"""

import json
import random
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bugs  # noqa: E402
from build import CANCEL_TEST, ci, failing, parse, project, run_ids  # noqa: E402

SEED = 7716
RUNNERS = {
    "ci-01": "UTC",
    "ci-02": "America/Los_Angeles",
    "ci-03": "Europe/Berlin",
    "ci-04": "Asia/Tokyo",
    "ci-05": "Pacific/Auckland",
    "ci-06": "America/Sao_Paulo",
}
# Release dates; a run uses the newest release out at its start.
RELEASES = [("2027-01-18", "2.6.0"), ("2027-01-27", "2.6.1"), ("2027-02-16", "2.6.2"), ("2027-03-09", "2.6.3")]
START = datetime(2027, 1, 18, 6, 0, tzinfo=timezone.utc)
END = datetime(2027, 3, 31, 23, 0, tzinfo=timezone.utc)
CANCELLED = 2


def release(now: datetime) -> str:
    return [v for d, v in RELEASES if d <= now.strftime("%Y-%m-%d")][-1]


def candidates(rng: random.Random):
    t = START
    run_id = 1180
    while True:
        t += timedelta(minutes=rng.randrange(600, 3600))
        if t > END:
            return
        run_id += rng.randrange(1, 9)
        runner = rng.choice(sorted(RUNNERS))
        yield {
            "id": run_id,
            "runner": runner,
            "tz": RUNNERS[runner],
            "seed": rng.randrange(1, 1_000_000),
            "hash_seed": rng.randrange(0, 4_294_967_296),
            "now": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "version": release(t),
        }


def main() -> None:
    runs_path, truth_path = Path(sys.argv[1]), Path(sys.argv[2])
    rng = random.Random(SEED)
    cands = list(candidates(rng))
    edits = list(bugs.SHIPPED) + ["D1"]
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        roots = {"ref": project(td / "ref", [])}
        for e in edits:
            roots[e] = project(td / e, [e])
        roots["ship"] = project(td / "ship", bugs.SHIPPED)
        roots["ship+D1"] = project(td / "ship-d1", bugs.SHIPPED + ["D1"])
        roots["B+D1"] = {b: project(td / f"{b}-d1", [b, "D1"]) for b in bugs.SHIPPED}

        def outcome(run):
            old = run["version"] == "2.6.0"
            ship = ci(roots["ship+D1" if old else "ship"], run)
            ref = ci(roots["ref"], run)
            single = {b: ci(roots["B+D1"][b] if old else roots[b], run) for b in bugs.SHIPPED}
            if old:
                single["D1"] = ci(roots["D1"], run)
            return ship, ref, single

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(outcome, cands))

        kept, why = [], {}
        for run, (ship, ref, single) in zip(cands, results):
            if failing(ref):
                raise SystemExit(f"correct package fails in run {run['id']}: {sorted(failing(ref))}")
            got = failing(ship)
            causes = {}
            for e, text in single.items():
                f = failing(text)
                if e != "D1" and run["version"] == "2.6.0":
                    f -= failing(single["D1"])
                causes[e] = f
            union = set().union(*causes.values())
            overlap = sum(len(f) for f in causes.values()) != len(union)
            if got != union or overlap:
                why[run["id"]] = "masked" if got != union else "overlap"
                continue
            kept.append((run, ship, causes))

        # Cancel two runs where the reprice test runs late, among runs that fail.
        late = [i for i, (run, ship, causes) in enumerate(kept)
                if any(causes.values()) and [t for _, t in parse(ship)[0]].index(CANCEL_TEST) > 40]
        for i in sorted(rng.sample(late, CANCELLED)):
            kept[i][0]["cancel"] = True

        truth = {e: {"tests": set(), "runs": []} for e in edits}
        for run, ship, causes in kept:
            k = [t for _, t in parse(ship)[0]].index(CANCEL_TEST) if run.get("cancel") else None
            shown = failing(ship, k)
            for e, f in causes.items():
                f &= shown
                if f:
                    truth[e]["tests"] |= f
                    truth[e]["runs"].append(run["id"])

        shipped = project(td / "lines", bugs.SHIPPED)
        out = {"causes": [], "decoys": {}}
        for b in bugs.SHIPPED:
            if len(truth[b]["runs"]) < 2:
                raise SystemExit(f"{b} shows in {len(truth[b]['runs'])} kept runs")
            out["causes"].append({
                "id": b,
                "class": bugs.CLASSES[b],
                "file": bugs.FILES[b],
                "lines": bugs.lines(shipped / "stockroom", b),
                "tests": sorted(truth[b]["tests"]),
                "runs": truth[b]["runs"],
            })
        out["decoys"] = {"D1": sorted(truth["D1"]["tests"]), "cancelled": [CANCEL_TEST]}
        all_cause_tests = set().union(*(set(c["tests"]) for c in out["causes"]))
        if all_cause_tests & (set(out["decoys"]["D1"]) | {CANCEL_TEST}):
            raise SystemExit("a decoy test also fails because of a shipped edit")
        out["dropped"] = why
    runs_path.write_text(json.dumps([r for r, _, _ in kept], indent=1) + "\n", encoding="utf-8")
    truth_path.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(f"{len(cands)} candidates, {len(kept)} kept, dropped {len(why)}")
    for c in out["causes"]:
        print(c["id"], c["class"], c["file"], c["lines"], len(c["runs"]), "runs", c["tests"])
    print("D1", out["decoys"]["D1"])


if __name__ == "__main__":
    main()
