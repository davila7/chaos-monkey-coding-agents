"""Trial runs: resolved engine configs per profile and task, Harbor commands, evidence.

    python -m cmca_harbor.trials plan --config cc-claude --seed <seed> --dataset datasets/cmca-n \
        --profile clean --profile moderate --attempts 1 --build <dir> --out <dir> [--jobs jobs]
    python -m cmca_harbor.trials plan --track s --config fx-claude --seed <seed> --dataset datasets/cmca-s \
        --profile clean --profile moderate --attempts 1 --out <dir> [--jobs jobs]
    python -m cmca_harbor.trials archive --config cc-claude --jobs jobs --dest results/<run>

One Harbor job per (profile, attempt), each running every task of the dataset
once with `attempt_index` passed through `--ak` (V-12).

On Track S the gateway in each task's compose file applies the faults, so no
injector is uploaded. Compose reads `TT_CONFIG_DIR` and `TT_ATTEMPT` from the
environment of `harbor run` (V-14), and each command carries them as an `env`
prefix. `--config oracle` and `--config nop` plan Harbor's built-in agents for
task validation.
"""

import argparse
import json
import shlex
import shutil
import sys
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from cmca_harbor.common import REPO_ROOT, RESOLVED_SCHEMA_PATH
from cmca_harbor.conformance import CATALOG_VERSION, task_chaos

PROFILES = REPO_ROOT / "profiles"
CONFIGS = REPO_ROOT / "configs"
CAPABILITIES = REPO_ROOT / "capabilities"

# Every service-layer type (SPEC 7.1): the gateway delivers the same bytes to
# every harness, so Track S needs no per-harness parity set.
TRACK_S_PARITY = ["deny", "err", "empty", "trunc", "falsefail", "poison", "drift", "latency", "rate"]
BUILTIN_AGENTS = ("oracle", "nop")


def load_config(config_id: str) -> dict[str, Any]:
    if config_id in BUILTIN_AGENTS:
        return {"harness": {"name": config_id, "version": "harbor", "harbor_agent": config_id}, "model": None}
    cfg = yaml.safe_load((CONFIGS / f"{config_id}.yaml").read_text())
    version = cfg["harness"]["version"]
    if version.startswith("<") or cfg["model"]["id"].startswith("<"):
        raise ValueError(f"configs/{config_id}.yaml: harness version and model id must be pinned before a run")
    return cfg


# Harbor's Pi and OpenCode agents take `provider/model`; Claude Code and fx
# take the config's id as it is.
PROVIDER_PREFIXED = ("pi", "opencode")
ROUTE_PROVIDER = {"anthropic-api": "anthropic"}
# Harbor option that carries `model.reasoning`. OpenCode's is the model
# variant (`opencode run --variant`); Pi's `thinking` accepts `reasoning_effort`.
REASONING_OPTION = {"opencode": "variant"}


def harbor_model(cfg: dict[str, Any]) -> str | None:
    """The `-m` value for Harbor, or None for its built-in agents."""
    model = cfg.get("model")
    if model is None:
        return None
    if cfg["harness"]["name"] in PROVIDER_PREFIXED and "/" not in model["id"]:
        return f"{ROUTE_PROVIDER[model['route']]}/{model['id']}"
    return model["id"]


def reasoning_kwargs(cfg: dict[str, Any]) -> list[tuple[str, str]]:
    """The harness's reasoning option for Harbor when the config pins one (D-0029)."""
    reasoning = (cfg.get("model") or {}).get("reasoning")
    if not reasoning or str(reasoning).startswith("<"):
        return []
    key = REASONING_OPTION.get((cfg.get("harness") or {}).get("name"), "reasoning_effort")
    return [(key, str(reasoning))]


def load_profile(name: str) -> dict[str, Any]:
    profile = yaml.safe_load((PROFILES / f"{name}.yaml").read_text())
    if profile.get("schema") != "tt-profile/2" or profile.get("name") != name:
        raise ValueError(f"profiles/{name}.yaml: expected schema tt-profile/2 named {name!r}")
    return profile


def capabilities(harness: str, version: str) -> dict[str, Any]:
    path = CAPABILITIES / f"{harness}@{version}.json"
    if not path.exists():
        raise FileNotFoundError(f"{path} missing; run conformance for this harness version first")
    return json.loads(path.read_text())


def tasks(dataset: Path) -> list[Path]:
    return sorted(p.parent for p in dataset.glob("*/task.toml"))


def engine_config(
    cfg: dict[str, Any], caps: dict[str, Any] | None, profile: dict[str, Any], seed: str, task_dir: Path
) -> dict[str, Any]:
    """`caps` None means Track S: service layer, the full service parity set, no gaps."""
    task, variants, sources = task_chaos(task_dir)
    h = cfg["harness"]
    out = {
        "schema": "tt-engine/1",
        "seed": seed,
        "trial_id": None,
        "task_id": task_dir.name,
        "attempt": 0,
        "harness": f"{h['name']}@{h['version']}",
        "layer": "native" if caps is not None else "service",
        "workspace_root": "/app",
        "profile": profile,
        "parity_set": caps["parity_set"] if caps is not None else TRACK_S_PARITY,
        "parity_gaps": [{"type": g["type"], "capability": g["capability"]} for g in (caps or {}).get("parity_gaps", [])],
        "catalog_version": CATALOG_VERSION,
        "task": task,
        "exempt_paths": [],
        "variants": variants,
        "sources": sources,
    }
    jsonschema.validate(out, json.loads(RESOLVED_SCHEMA_PATH.read_text()))
    return out


def plan(
    config_id: str,
    seed: str,
    dataset: Path,
    profiles: list[str],
    attempts: int,
    build: Path | None,
    out: Path,
    jobs: Path,
    track: str = "n",
) -> list[list[str]]:
    """Writes `out/<profile>/<task>.json` and returns one Harbor command per (profile, attempt).

    `clean` also runs with the injector loaded, at base rate 0, so both arms
    share one installation and the clean arm logs every eligible call (the
    exposure floor of SPEC 10.3 is read from those records).
    """
    cfg = load_config(config_id)
    h = cfg["harness"]
    if track == "n" and (config_id in BUILTIN_AGENTS or build is None):
        raise ValueError("Track N runs need a harness config and --build")
    caps = capabilities(h["name"], h["version"]) if track == "n" else None
    task_dirs = tasks(dataset)
    if not task_dirs:
        raise ValueError(f"{dataset}: no tasks")
    commands = []
    for name in profiles:
        profile = load_profile(name)
        cfg_dir = out / name
        cfg_dir.mkdir(parents=True, exist_ok=True)
        for t in task_dirs:
            (cfg_dir / f"{t.name}.json").write_text(json.dumps(engine_config(cfg, caps, profile, seed, t), indent=2))
        for a in range(attempts):
            argv = ["harbor", "run", "-p", str(dataset), "-a", h["harbor_agent"]]
            if (model := harbor_model(cfg)) is not None:
                argv += ["-m", model]
            argv += ["-k", "1", "-o", str(jobs), "--job-name", f"{config_id}-{name}-a{a}", "-y"]
            if track == "n":
                aks = (("attempt_index", a), ("tt_config_dir", cfg_dir), ("tt_build_dir", build), ("version", h["version"]))
            else:
                argv = ["env", f"TT_CONFIG_DIR={cfg_dir}", f"TT_ATTEMPT={a}", *argv]
                aks = () if config_id in BUILTIN_AGENTS else (("attempt_index", a), ("version", h["version"]))
            for k, v in (*aks, *reasoning_kwargs(cfg)):
                argv += ["--ak", f"{k}={v}"]
            commands.append(argv)
    return commands


# Per-trial files the analysis reads. Everything else in a job directory
# (session logs, harness caches) stays out of the repository.
EVIDENCE = (
    "config.json",
    "result.json",
    "agent/trajectory.json",
    "agent/tt/events.jsonl",
    "agent/fx.json",
    "agent/fx-session/events.jsonl",
    "agent/fx-session/usage-v2.json",
    "artifacts/var/log/tt/events.jsonl",
    "artifacts/var/log/tt/gateway.jsonl",
    "artifacts/var/lib/tickets/state.json",
    "artifacts/var/lib/inventory/state.json",
    "artifacts/var/lib/deploy/state.json",
    "artifacts/app/count-exceptions.txt",
    "artifacts/app/shortfall.csv",
    "artifacts/app/blocked.csv",
    "artifacts/app/STATUS.json",
    "artifacts/app/report.json",
    "verifier/reward.txt",
    "verifier/STATUS.json",
    "verifier/check.txt",
    "verifier/unittest.txt",
)


def archive(config_id: str, jobs: Path, dest: Path) -> int:
    """Copies the evidence of every trial in the `<config_id>-*` jobs under `jobs` to `dest`."""
    copied = 0
    for job in sorted(p for p in jobs.iterdir() if p.is_dir() and p.name.startswith(f"{config_id}-")):
        for trial in sorted(p for p in job.iterdir() if p.is_dir() and (p / "config.json").exists()):
            for rel in EVIDENCE:
                src = trial / rel
                if src.exists():
                    out = dest / job.name / trial.name / rel
                    out.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(src, out)
                    copied += 1
    return copied


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="cmca_harbor.trials")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan", help="write engine configs and print Harbor commands")
    p.add_argument("--config", required=True, help="config id under configs/")
    p.add_argument("--seed", required=True)
    p.add_argument("--dataset", required=True, type=Path)
    p.add_argument("--profile", action="append", required=True)
    p.add_argument("--attempts", type=int, default=1)
    p.add_argument("--track", choices=["n", "s"], default="n")
    p.add_argument("--build", type=Path, help="built injector layout (bin/ and the harness folder); Track N only")
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--jobs", type=Path, default=Path("jobs"))
    a = sub.add_parser("archive", help="copy trial evidence out of the job directories")
    a.add_argument("--config", required=True)
    a.add_argument("--jobs", required=True, type=Path)
    a.add_argument("--dest", required=True, type=Path)
    args = ap.parse_args(argv)
    if args.cmd == "archive":
        print(f"{archive(args.config, args.jobs, args.dest)} evidence files")
        return 0
    for cmd in plan(
        args.config, args.seed, args.dataset.resolve(), args.profile, args.attempts,
        args.build.resolve() if args.build else None, args.out.resolve(), args.jobs, args.track,
    ):
        print(shlex.join(cmd))
    return 0


if __name__ == "__main__":
    sys.exit(main())
