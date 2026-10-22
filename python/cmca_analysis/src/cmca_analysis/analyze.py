"""Release analysis: committed job directories to board summaries and site data (SPEC 9.7, D-0032).

    python -m cmca_analysis analyze --release <name> --seed <seed> \\
        --evidence results/<run> [--evidence ...] --out results/<release> [--site packages/site/data/results.json]

Boards follow SPEC 6.4: `track-s` holds every config with Track S trials;
`track-n-fixed` and `track-n-native` hold Track N trials of configs on that axis
(`cc-claude` is on both). A row needs `clean` and `moderate` trials. Outputs are
byte-identical for identical inputs and seed.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any, Callable, Sequence

import yaml

from . import metrics as m
from .classify import TrialAnalysis, analyze_trial
from .ingest import DATASETS, REPO_ROOT, TaskDecl, Trial, load_trial, payload_texts, settled_costs, task_decls, trial_dirs
from .reconcile import reconcile
from .rules import Rules, load_rules
from .stats import REPLICATES, Unit, bootstrap, holm, paired_permutation, paired_power, rank_bands
from .validate import validate

SCHEMA = "cmca-config-summary/1"
BOARDS = (
    ("track-s", "Track S", "Service layer. An MCP proxy in front of mock services delivers the same bytes to every harness."),
    (
        "track-n-fixed",
        "Track N fixed model",
        "Built-in tools, same model in every harness. Faults come from each harness's own hooks; "
        "rows compare only within the fixed-model parity set (SPEC 6.4).",
    ),
    (
        "track-n-native",
        "Track N native pairs",
        "Built-in tools, each vendor's own harness and model. Rows compare only within the native-pairs parity set (SPEC 6.4).",
    ),
)
CURVE_PROFILES = ("clean", "light", "moderate", "heavy")
DECIMALS = 4


@dataclass
class Config:
    id: str
    harness: str
    version: str
    model: str
    route: str
    reasoning: str | None
    axes: list[str]
    tracks: list[str]


def load_configs(directory: Path) -> dict[str, Config]:
    out = {}
    for p in sorted(directory.glob("*.yaml")):
        d = yaml.safe_load(p.read_text())
        reasoning = d["model"].get("reasoning")
        out[d["id"]] = Config(
            id=d["id"],
            harness=d["harness"]["name"],
            version=str(d["harness"]["version"]),
            model=d["model"]["id"],
            route=d["model"]["route"],
            reasoning=None if not reasoning or reasoning.startswith("<") else reasoning,
            axes=list(d["axes"]),
            tracks=list(d["tracks"]),
        )
    return out


def base_rates(directory: Path) -> dict[str, float]:
    return {p.stem: float(yaml.safe_load(p.read_text())["base_rate"]) for p in sorted(directory.glob("*.yaml"))}


def board_of(board: str, trial: Trial, config: Config | None) -> bool:
    if board == "track-s":
        return trial.track == "s"
    if trial.track != "n" or config is None:
        return False
    return ("fixed" if board == "track-n-fixed" else "native") in config.axes


def rounded(x: Any) -> Any:
    if isinstance(x, float):
        return round(x, DECIMALS)
    if isinstance(x, dict):
        return {k: rounded(v) for k, v in x.items()}
    if isinstance(x, list):
        return [rounded(v) for v in x]
    return x


def _units(trials: Sequence[Trial]) -> list[Unit[Trial]]:
    """One unit per task: profile to valid trials, ordered by attempt and trial name."""
    tasks = sorted({t.task for t in trials})
    out: list[Unit[Trial]] = []
    for task in tasks:
        unit: Unit[Trial] = {}
        for t in sorted((t for t in trials if t.task == task and not t.excluded), key=lambda t: (t.attempt or 0, t.trial)):
            unit.setdefault(t.profile, []).append(t)
        out.append(unit)
    return out


def _groups(units: Sequence[Unit[Trial]], profile: str) -> list[list[Trial]]:
    return [u.get(profile, []) for u in units]


def _flat(units: Sequence[Unit[Trial]], profile: str) -> list[Trial]:
    return [t for u in units for t in u.get(profile, [])]


def _boot_stats(decls: dict[str, TaskDecl], profiles: Sequence[str]) -> dict[str, Callable[[Sequence[Unit[Trial]]], float | None]]:
    stats: dict[str, Callable[[Sequence[Unit[Trial]]], float | None]] = {
        f"pass1:{p}": (lambda us, p=p: m.pass1(_groups(us, p))) for p in profiles
    }
    stats["rr"] = lambda us: m.retention(_groups(us, "clean"), _groups(us, "moderate"))[0]
    stats["pass3:moderate"] = lambda us: m.pass_k(_groups(us, "moderate"), 3)
    stats["overclaim:moderate"] = lambda us: m.overclaim(_flat(us, "moderate"))
    stats["poison:moderate"] = lambda us: m.poison_rate(_flat(us, "moderate"), decls)
    return stats


def _profile_summary(
    trials: list[Trial], valid_groups: list[list[Trial]], analyses: dict[str, TrialAnalysis], decls: dict[str, TaskDecl]
) -> dict[str, Any]:
    valid = [t for t in trials if not t.excluded]
    an = [analyses[t.path] for t in valid]
    poison_d, poison_p = m.poison_propagation(valid, decls)
    dsr_n, dsr_dup = m.duplicate_rate(valid, decls)
    costs = [t.cost_usd for t in trials if t.cost_usd is not None]
    return {
        "trials": len(trials),
        "tasks": len([g for g in valid_groups if g]),
        "pass1": m.pass1(valid_groups),
        "successes": sum(1 for t in valid if t.success),
        "valid_trials": len(valid),
        "pass3": m.pass_k(valid_groups, 3),
        "outcomes": m.outcome_distribution(an),
        "event_recovery_rate": m.event_recovery_rate(an),
        "report": m.report_rates(valid),
        "poison": {"delivered": poison_d, "propagated": poison_p, "rate": poison_p / poison_d if poison_d else None},
        "duplicate_side_effect": {"trials": dsr_n, "duplicated": dsr_dup, "rate": dsr_dup / dsr_n if dsr_n else None},
        "pathologies": m.pathology_rates(an),
        "destructive": sorted({h for a in an for h in a.destructive}),
        "validity": m.validity(trials),
        "by_fault_type": m.by_fault_type(an, trials),
        "cost_usd_total": sum(costs) if costs else None,
        "cost_sources": sorted({t.cost_source or "none" for t in trials}),
        "dollars_per_success": m.dollars_per_success(valid),
        "tokens_total": sum((t.input_tokens or 0) + (t.output_tokens or 0) for t in trials),
    }


def summarize_config(
    board: str,
    config_id: str,
    trials: list[Trial],
    analyses: dict[str, TrialAnalysis],
    decls: dict[str, TaskDecl],
    rates: dict[str, float],
    seed: str,
    replicates: int,
) -> dict[str, Any]:
    profiles = sorted({t.profile for t in trials})
    units = _units(trials)
    point = {
        p: _profile_summary([t for t in trials if t.profile == p], _groups(units, p), analyses, decls) for p in profiles
    }
    boot = bootstrap(units, _boot_stats(decls, profiles), f"{seed}|{board}|{config_id}", replicates)
    rr, delta = m.retention(_groups(units, "clean"), _groups(units, "moderate"))
    curve_pts = {rates[p]: point[p]["pass1"] for p in CURVE_PROFILES if p in point and p in rates and point[p]["pass1"] is not None}
    clean = [t for t in trials if t.profile == "clean" and not t.excluded]
    moderate = [t for t in trials if t.profile == "moderate" and not t.excluded]
    return {
        "schema": SCHEMA,
        "board": board,
        "config_id": config_id,
        "profiles": point,
        "intervals": boot,
        "retention": {"rr": rr, "delta": delta},
        "robustness_auc": m.robustness_auc(curve_pts),
        "cost_inflation": m.cost_inflation(clean, moderate) if clean and moderate else None,
        "tasks": sorted({t.task for t in trials}),
        "trial_links": sorted(t.path for t in trials),
        "trial_problems": {t.path: t.problems for t in sorted(trials, key=lambda t: t.path) if t.problems},
    }


def _interval(b: dict[str, Any] | None) -> dict[str, float] | None:
    return None if b is None else {"value": b["value"], "lo": b["lo"], "hi": b["hi"]}


def site_row(summary: dict[str, Any], config: Config, rates: dict[str, float]) -> dict[str, Any] | None:
    iv = summary["intervals"]
    if not iv.get("pass1:moderate") or not iv.get("pass1:clean"):
        return None
    mod = summary["profiles"]["moderate"]
    curve = [
        {"profile": p, "base_rate": rates[p], "pass1": _interval(iv[f"pass1:{p}"])}
        for p in CURVE_PROFILES
        if iv.get(f"pass1:{p}") and p in rates
    ]
    trials = sum(s["trials"] for s in summary["profiles"].values())
    excluded = sum(s["validity"]["excluded"] for s in summary["profiles"].values())
    return {
        "config_id": config.id,
        "harness": {"name": config.harness, "version": config.version},
        "model": {"id": config.model, "route": config.route, "reasoning": config.reasoning},
        "axis": "fixed" if "fixed" in config.axes and summary["board"] != "track-n-native" else "native",
        "trials": trials,
        "excluded": excluded,
        "metrics": {
            "faulted_success": _interval(iv["pass1:moderate"]),
            "clean_pass1": _interval(iv["pass1:clean"]),
            "rr": _interval(iv.get("rr")),
            "pass3_moderate": _interval(iv.get("pass3:moderate")),
            "overclaim_rate": _interval(iv.get("overclaim:moderate")),
            "poison_propagation_rate": _interval(iv.get("poison:moderate")),
            "dollars_per_success": mod["dollars_per_success"],
            "tokens_total": mod["tokens_total"],
        },
        "faulted_counts": {"succeeded": mod["successes"], "sent": mod["valid_trials"]},
        "curve": curve if len(curve) > 2 else None,
        "trial_links": summary["trial_links"],
    }


def compare(summaries: dict[str, dict[str, Any]], units: dict[str, list[Unit[Trial]]], seed: str, board: str, replicates: int) -> list[dict[str, Any]]:
    """Paired permutation tests on per-task Faulted Success, Holm-corrected within the board."""
    rows = []
    for a, b in combinations(sorted(summaries), 2):
        ua = {next(iter(u.values()))[0].task: u for u in units[a] if u}
        ub = {next(iter(u.values()))[0].task: u for u in units[b] if u}
        diffs = []
        for task in sorted(set(ua) & set(ub)):
            ta, tb = ua[task].get("moderate", []), ub[task].get("moderate", [])
            if ta and tb:
                diffs.append(m.task_pass1(ta) - m.task_pass1(tb))
        p = paired_permutation(diffs, f"{seed}|{board}|{a}|{b}", replicates)
        outcomes = [
            ([float(bool(t.success)) for t in ua[task].get("moderate", [])], [float(bool(t.success)) for t in ub[task].get("moderate", [])])
            for task in sorted(set(ua) & set(ub))
        ]
        rows.append({
            "a": a, "b": b, "tasks": len(diffs), "mean_difference": sum(diffs) / len(diffs) if diffs else None, "p": p,
            "power": paired_power([x for x, _ in outcomes], [y for _, y in outcomes]),
        })
    adjusted = holm({f"{r['a']}|{r['b']}": r["p"] for r in rows})
    for r in rows:
        r["p_holm"] = adjusted[f"{r['a']}|{r['b']}"]
    return rows


def not_measurable(configs: dict[str, Config], present: set[str], rules: Rules) -> list[dict[str, str]]:
    """Configs in this release that belong to a board's axis but do not run on its track."""
    out = []
    for board, _, _ in BOARDS:
        track = "s" if board == "track-s" else "n"
        for cid in sorted(present):
            c = configs.get(cid)
            if c is None or track in c.tracks:
                continue
            if board == "track-n-fixed" and "fixed" not in c.axes or board == "track-n-native" and "native" not in c.axes:
                continue
            reason = rules.track_exclusions.get(cid, {}).get(track, rules.track_exclusion_default)
            out.append({"board": board, "config_id": cid, "reason": reason})
    return out


@dataclass
class Release:
    boards: dict[str, dict[str, Any]]
    summaries: dict[tuple[str, str], dict[str, Any]]
    site: dict[str, Any]


def analyze(
    evidence: Sequence[Path],
    release: str,
    seed: str,
    replicates: int = REPLICATES,
    datasets: Sequence[Path] = DATASETS,
    configs_dir: Path = REPO_ROOT / "configs",
    profiles_dir: Path = REPO_ROOT / "profiles",
) -> Release:
    rules = load_rules()
    decls = task_decls(list(datasets))
    payloads = payload_texts()
    configs = load_configs(configs_dir)
    rates = base_rates(profiles_dir)
    trials: list[Trial] = []
    analyses: dict[str, TrialAnalysis] = {}
    for ev in evidence:
        settled = settled_costs(ev)
        for d in trial_dirs(ev):
            t = load_trial(d, ev, decls, settled)
            decl = decls.get(t.task, TaskDecl())
            reconcile(t, payloads, decl.token, decl.stale)
            t.problems = validate(t, d)
            analyses[t.path] = analyze_trial(t, decl, rules)
            trials.append(t)

    boards: dict[str, dict[str, Any]] = {}
    summaries: dict[tuple[str, str], dict[str, Any]] = {}
    site_boards = []
    for board, title, description in BOARDS:
        mine = [t for t in trials if board_of(board, t, configs.get(t.config_id))]
        by_config = {cid: [t for t in mine if t.config_id == cid] for cid in sorted({t.config_id for t in mine})}
        board_summaries = {
            cid: summarize_config(board, cid, ts, analyses, decls, rates, seed, replicates) for cid, ts in by_config.items()
        }
        rows = []
        for cid, s in board_summaries.items():
            summaries[(board, cid)] = s
            row = site_row(s, configs[cid], rates) if cid in configs else None
            if row:
                rows.append(row)
        ranked = {r["config_id"] for r in rows}
        comparisons = compare(
            {c: s for c, s in board_summaries.items() if c in ranked},
            {c: _units(ts) for c, ts in by_config.items()},
            seed,
            board,
            replicates,
        )
        bands = rank_bands([r["metrics"]["faulted_success"] for r in rows])
        boards[board] = {
            "schema": "cmca-board/1",
            "board": board,
            "release": release,
            "configs": sorted(board_summaries),
            "rows": sorted(r["config_id"] for r in rows),
            "bands": {r["config_id"]: b for r, b in zip(rows, bands)},
            "comparisons": comparisons,
        }
        # Native pairs compare vendors' own harness and model; one config is not a pair yet (METHODOLOGY 7).
        if mine and not (board == "track-n-native" and len(rows) < 2):
            site_boards.append({"id": board, "title": title, "description": description, "rows": rows})

    finished = sorted(t.finished_at for t in trials if t.finished_at)
    site = {
        "schema": "site-data/1",
        "kind": "release",
        "release": release,
        "generated_at": finished[-1] if finished else None,
        "source": f"results/{release}",
        "boards": site_boards,
        "not_measurable": not_measurable(configs, {t.config_id for t in trials}, rules),
    }
    meta = {"seed": seed, "replicates": replicates, "rules": rules.versions, "evidence": [_rel(e) for e in evidence]}
    for b in boards.values():
        b["meta"] = meta
    for s in summaries.values():
        s["meta"] = meta
    return Release(boards=rounded(boards), summaries=rounded(summaries), site=rounded(site))


def _rel(p: Path) -> str:
    try:
        return str(p.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return p.name


def write(rel: Release, out: Path, site: Path | None) -> list[Path]:
    written = []
    for board, data in rel.boards.items():
        p = out / board / "board.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(m.dumps(data))
        written.append(p)
    for (board, cid), data in rel.summaries.items():
        p = out / board / cid / "summary.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(m.dumps(data))
        written.append(p)
    p = out / "site-data.json"
    p.write_text(m.dumps(rel.site))
    written.append(p)
    if site:
        site.write_text(m.dumps(rel.site))
        written.append(site)
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="cmca_analysis analyze")
    ap.add_argument("--release", required=True)
    ap.add_argument("--seed", required=True)
    ap.add_argument("--evidence", required=True, type=Path, action="append")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--site", type=Path, help="also write site-data/1 here, e.g. packages/site/data/results.json")
    ap.add_argument("--replicates", type=int, default=REPLICATES)
    args = ap.parse_args(argv)
    rel = analyze(args.evidence, args.release, args.seed, args.replicates)
    for p in write(rel, args.out, args.site):
        print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
