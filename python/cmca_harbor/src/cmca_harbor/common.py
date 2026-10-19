import json
import shlex
import tempfile
from pathlib import Path
from typing import Any

import jsonschema
from pydantic import BaseModel, Field

REMOTE_ROOT = "/opt/tt"
REMOTE_CONFIG = f"{REMOTE_ROOT}/config.json"
REMOTE_STATE = f"{REMOTE_ROOT}/state"
REMOTE_LOG_DIR = "/logs/agent/tt"
REMOTE_LOG = f"{REMOTE_LOG_DIR}/events.jsonl"
REMOTE_CA = f"{REMOTE_ROOT}/ca.crt"

REPO_ROOT = Path(__file__).resolve().parents[4]
RESOLVED_SCHEMA_PATH = REPO_ROOT / "packages/fault-engine/schemas/tt-engine-1.resolved.schema.json"


class TtOptions(BaseModel):
    """Options every CMCA agent declares so Harbor accepts them through `--ak`."""

    attempt_index: int | None = Field(default=None)
    # Host directory holding one resolved engine config per task, `<task>.json`,
    # written by `cmca plan`. Absent means the harness runs without the injector.
    tt_config_dir: str | None = Field(default=None)
    # Host directory with the built injector layout (`bin/`, plugin folders).
    tt_build_dir: str | None = Field(default=None)
    # Host PEM bundle for hosts whose egress re-terminates TLS (claude.ai cloud
    # sessions). Node reads it through NODE_EXTRA_CA_CERTS; verification stays on.
    extra_ca_cert: str | None = Field(default=None)


def trial_task_name(logs_dir: Path) -> str:
    """Task directory name of the trial that owns `logs_dir` (`<trial>/agent`)."""
    trial_dir = logs_dir.parent
    config = trial_dir / "config.json"
    if config.exists():
        path = json.loads(config.read_text()).get("task", {}).get("path")
        if path:
            return Path(path).name
    return trial_dir.name.rsplit("__", 1)[0]


def engine_config(config_dir: Path, task: str, attempt: int, trial_id: str) -> dict[str, Any]:
    """The task's resolved engine config with this trial's attempt and id.

    Validated against the resolved schema before upload: `tt-decide` cannot
    apply defaults itself, and an unresolved config would otherwise only show
    up as error records inside the trial.
    """
    path = config_dir / f"{task}.json"
    cfg = {**json.loads(path.read_text()), "attempt": attempt, "trial_id": trial_id}
    if cfg.get("task_id") != task:
        raise ValueError(f"{path}: task_id {cfg.get('task_id')!r} does not match task {task!r}")
    schema = json.loads(RESOLVED_SCHEMA_PATH.read_text())
    try:
        jsonschema.validate(cfg, schema)
    except jsonschema.ValidationError as e:
        where = "/".join(str(p) for p in e.absolute_path) or "<root>"
        raise ValueError(f"{path}: not a resolved tt-engine/1 config at {where}: {e.message}") from None
    return cfg


def read_events(logs_dir: Path) -> list[dict[str, Any]]:
    path = logs_dir / "tt" / "events.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


class TtAgentMixin:
    """Injector setup shared by the CMCA Harbor agents.

    A subclass names the folder of its harness under the build layout
    (`HARNESS_DIR`). Without `tt_config_dir` nothing is uploaded and the
    harness runs unmodified, which is the `clean` baseline with an identical
    installation.
    """

    HARNESS_DIR: str

    def _tt_active(self) -> bool:
        return bool(self.options.tt_config_dir)

    async def _tt_prepare(self, environment) -> dict[str, str]:
        """Uploads the injector and config; returns the env for the harness process."""
        opts = self.options
        if not opts.tt_config_dir:
            return {}
        if opts.attempt_index is None:
            raise ValueError("attempt_index is required when tt_config_dir is set")
        if not opts.tt_build_dir:
            raise ValueError("tt_build_dir is required when tt_config_dir is set")
        build = Path(opts.tt_build_dir)
        for required in ("bin/tt-decide.cjs", self.HARNESS_DIR):
            if not (build / required).exists():
                raise FileNotFoundError(f"{build / required} missing; run `pnpm build`")
        task = trial_task_name(self.logs_dir)
        cfg = engine_config(Path(opts.tt_config_dir), task, opts.attempt_index, self.logs_dir.parent.name)

        await self.exec_as_root(environment, command=f"mkdir -p {REMOTE_ROOT} {REMOTE_LOG_DIR}")
        await environment.upload_dir(build / "bin", f"{REMOTE_ROOT}/bin")
        await environment.upload_dir(build / self.HARNESS_DIR, f"{REMOTE_ROOT}/{self.HARNESS_DIR}")
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp) / "config.json"
            local.write_text(json.dumps(cfg))
            await environment.upload_file(local, REMOTE_CONFIG)
        owner = environment.default_user
        chown = f"chown -R {shlex.quote(str(owner))} {REMOTE_ROOT} {REMOTE_LOG_DIR} && " if owner is not None else ""
        await self.exec_as_root(
            environment,
            command=f"{chown}mkdir -p {REMOTE_STATE} && chmod -R a+rX {REMOTE_ROOT}",
        )
        return {"TT_CONFIG": REMOTE_CONFIG, "TT_STATE": REMOTE_STATE, "TT_LOG": REMOTE_LOG}

    async def _ca_env(self, environment) -> dict[str, str]:
        """Uploads `extra_ca_cert`, if set, and returns the env that makes Node trust it."""
        if not self.options.extra_ca_cert:
            return {}
        await self.exec_as_root(environment, command=f"mkdir -p {REMOTE_ROOT}")
        await environment.upload_file(Path(self.options.extra_ca_cert), REMOTE_CA)
        await self.exec_as_root(environment, command=f"chmod a+r {REMOTE_CA}")
        return {"NODE_EXTRA_CA_CERTS": REMOTE_CA}

    async def _ca_env_and_system_bundle(self, environment) -> dict[str, str]:
        """`_ca_env`, plus the CA appended to the system bundle for curl and
        for binaries that read it instead of NODE_EXTRA_CA_CERTS."""
        ca = await self._ca_env(environment)
        if ca:
            bundle = "/etc/ssl/certs/ca-certificates.crt"
            marker = f"{REMOTE_ROOT}/ca-appended"
            await self.exec_as_root(
                environment,
                command=f"if [ -f {bundle} ] && [ ! -e {marker} ]; then cat {REMOTE_CA} >> {bundle} && touch {marker}; fi",
            )
        return ca

    def _tt_metadata(self, context) -> None:
        events = read_events(self.logs_dir)
        metadata = dict(context.metadata or {})
        metadata["tt"] = {
            "events": len(events),
            "applied": sum(1 for e in events if e.get("decision") == "apply"),
            "errors": sum(1 for e in events if e.get("decision") == "error"),
        }
        context.metadata = metadata
