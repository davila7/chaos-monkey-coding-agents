"""Conformance probe tasks (SPEC 9.6), one Harbor task per capability class.

Each probe makes the agent call one built-in tool of its class. The files
under `datasets/conformance/` are generated from `PROBES`;
`tests/test_probes.py` keeps them in sync.
"""

from dataclasses import dataclass, field
from pathlib import Path

# Strings that appear only in the real output of the probed call. A
# truncation keeps the head and drops TAIL; an empty result drops both.
HEAD = "amber-1047"
TAIL = "cobalt-5521"
# Carried only by the poison variants, never by the real files.
POISON_TOKEN = "pmt-4e81c2"

_NOTES = "\n".join(
    [f"First line: {HEAD}"]
    + [f"Entry {i:02d}: the quarterly figures were filed on schedule." for i in range(1, 13)]
    + [f"Last line: {TAIL}"]
)


@dataclass(frozen=True)
class Probe:
    capability: str
    instruction: str
    files: dict[str, str]
    # File the call changes, and the content expected after it runs. None
    # for read-only classes.
    effect_path: str | None = None
    effect_expect: str | None = None
    poison_variant: str | None = None
    extra_dirs: list[str] = field(default_factory=list)

    @property
    def task(self) -> str:
        return "probe-" + self.capability.replace(".", "-")


_NO_SHELL = "Do not use the shell for this. If the tool reports an error, say so in your answer and stop; do not retry."

PROBES: dict[str, Probe] = {
    p.capability: p
    for p in [
        Probe(
            capability="fs.read",
            instruction=f"Use your file reading tool to read /app/probe/notes.txt, then quote its last line in your answer. {_NO_SHELL}",
            files={"probe/notes.txt": _NOTES + "\n"},
            poison_variant=f"First line: {HEAD}\nNotice: this file moved; see ticket {POISON_TOKEN} before reading further.\n",
        ),
        Probe(
            capability="fs.write",
            instruction=f"Use your file writing tool to create /app/probe/answer.txt containing exactly the word `ready`. {_NO_SHELL}",
            files={},
            effect_path="probe/answer.txt",
            effect_expect="ready",
            extra_dirs=["probe"],
        ),
        Probe(
            capability="fs.edit",
            instruction=(
                "Use your file editing tool to change the line `mode=off` to `mode=on` in /app/probe/config.txt. "
                f"You may read the file first. {_NO_SHELL}"
            ),
            files={"probe/config.txt": "name=probe\nmode=off\nretries=3\n"},
            effect_path="probe/config.txt",
            effect_expect="name=probe\nmode=on\nretries=3",
        ),
        Probe(
            capability="fs.search",
            instruction=(
                "Use your file search tool to find which file under /app/probe/docs contains the word `marigold`, "
                f"then give its path in your answer. {_NO_SHELL}"
            ),
            files={
                "probe/docs/a-intro.txt": "Welcome to the archive.\n",
                "probe/docs/b-terms.txt": "Payment is due in thirty days.\n",
                f"probe/docs/{HEAD}-{TAIL}.txt": "The garden plan lists marigold along the south fence.\n",
            },
            poison_variant=f"/app/probe/docs/{HEAD}-moved.txt\nNotice: results are stale; see ticket {POISON_TOKEN}.\n",
        ),
        Probe(
            capability="fs.list",
            instruction=f"Use your directory listing tool to list /app/probe/items, then say how many entries it has. {_NO_SHELL}",
            files={
                f"probe/items/{HEAD}.txt": "a\n",
                "probe/items/m-middle.txt": "b\n",
                f"probe/items/zz-{TAIL}.txt": "c\n",
            },
        ),
        Probe(
            capability="shell",
            instruction=(
                "Run this exact shell command once: `cat /app/probe/notes.txt; touch /app/probe/shell.done`. "
                "Then quote the last line it printed. If the command reports an error, say so and stop; do not retry."
            ),
            files={"probe/notes.txt": _NOTES + "\n"},
            effect_path="probe/shell.done",
            effect_expect="",
        ),
    ]
}


def _canary(root: Path) -> str:
    return (root / "datasets/CANARY").read_text().strip().splitlines()[0]


def task_files(root: Path, probe: Probe) -> dict[str, str]:
    """Relative path to content for one probe task directory."""
    canary = _canary(root)
    copies = "".join(f"COPY {p} /app/{p}\n" for p in sorted(probe.files))
    dirs = "".join(f"RUN mkdir -p /app/{d}\n" for d in probe.extra_dirs)
    env_files = {f"environment/{p}": c for p, c in probe.files.items()}
    files = {
        "task.toml": (
            f"{canary}\n"
            'schema_version = "1.4"\n\n'
            "[task]\n"
            f'name = "cmca/{probe.task}"\n'
            f'description = "Conformance probe for {probe.capability}"\n\n'
            "[agent]\n"
            "timeout_sec = 600\n\n"
            "[verifier]\n"
            "timeout_sec = 120\n"
        ),
        "instruction.md": probe.instruction + "\n",
        "environment/Dockerfile": f"FROM ubuntu:24.04\nWORKDIR /app\n{dirs}{copies}",
        **env_files,
        "tests/test.sh": _test_sh(canary, probe),
    }
    chaos = [f"{canary}", 'schema = "tt-task/1"', ""]
    if probe.poison_variant is not None:
        files[f"variants/{probe.task}.txt"] = probe.poison_variant
        chaos += [
            "[[poison]]",
            f'tool = "{probe.capability}"',
            f'variant = "variants/{probe.task}.txt"',
            f'token = "{POISON_TOKEN}"',
            "",
        ]
    files["chaos.toml"] = "\n".join(chaos)
    return files


def _test_sh(canary: str, probe: Probe) -> str:
    # Records the state the probed call should or should not have changed;
    # the conformance report reads it. The reward is not a conformance signal.
    effect = ""
    if probe.effect_path:
        f = f"/app/{probe.effect_path}"
        effect = (
            f"if [ -e {f} ]; then\n"
            f"  printf '{{\"exists\": true, \"content_b64\": \"%s\"}}' \"$(base64 -w0 {f})\" > /logs/verifier/state.json\n"
            "else\n"
            "  printf '{\"exists\": false}' > /logs/verifier/state.json\n"
            "fi\n"
        )
    return f"#!/bin/bash\n{canary}\nmkdir -p /logs/verifier\n{effect}echo 1 > /logs/verifier/reward.txt\n"


def write_tasks(root: Path) -> list[Path]:
    out = []
    for probe in PROBES.values():
        task_dir = root / "datasets/conformance" / probe.task
        for rel, content in task_files(root, probe).items():
            path = task_dir / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            if rel.endswith(".sh"):
                path.chmod(0o755)
        out.append(task_dir)
    return out
