"""Builds the /app tree: the stockroom package, its tests, tools, docs and the
CI logs.

Usage: python3 build.py OUT_DIR

Every log is the output of tools/ci.py run on a copy of the shipped tree with
the parameters of runs.json (plan.py draws them), so replaying a logged run
in /app gives the same results, except for runs of 2.6.0, whose copy also
carries D1, and for cancelled runs, whose output stops at the test that was
running when the run was cancelled. The output depends only on runs.json and
the files next to this script.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bugs  # noqa: E402

CANCEL_TEST = "tests.test_rates.BulkTests.test_reprice_catalog"


def copy_tree(src: Path, dst: Path) -> None:
    for p in sorted(src.rglob("*")):
        if "__pycache__" in p.parts:
            continue
        rel = p.relative_to(src)
        if p.is_dir():
            (dst / rel).mkdir(parents=True, exist_ok=True)
        else:
            (dst / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, dst / rel)


def project(dst: Path, ids, version: str = "2.6.3") -> Path:
    """A copy of the package, its tests and tools with the named edits."""
    for name in ("stockroom", "tests", "tools"):
        copy_tree(HERE / "src" / name, dst / name)
    bugs.apply(dst / "stockroom", ids)
    init = dst / "stockroom" / "__init__.py"
    init.write_text(init.read_text(encoding="utf-8").replace('__version__ = "2.6.3"', f'__version__ = "{version}"'), encoding="utf-8")
    return dst


def ci(root: Path, run: dict, extra=()) -> str:
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONHASHSEED", "TZ", "STOCKROOM_NOW", "TMPDIR")}
    argv = [sys.executable, "-B", "tools/ci.py", "--seed", str(run["seed"]), "--hash-seed", str(run["hash_seed"]),
            "--tz", run["tz"], "--now", run["now"], "--runner", run["runner"], "--run-id", str(run["id"]), *extra]
    r = subprocess.run(argv, cwd=root, env=env, capture_output=True, text=True, timeout=600)
    if r.returncode not in (0, 1) or r.stderr.strip():
        raise SystemExit(f"run {run['id']}: ci.py exited {r.returncode}: {r.stderr[-2000:]}")
    return r.stdout


def parse(text: str) -> tuple[list[tuple[str, str]], dict[str, str]]:
    """(status, test id) per test line, and the failure block of each failed test."""
    statuses = re.findall(r"^(ok|FAIL|ERROR|skip) +(tests\.\S+)$", text, re.M)
    blocks = {}
    for m in re.finditer(r"^---- (?:FAIL|ERROR): (\S+)\n(.*?)(?=^---- |^\n?result: |\Z)", text, re.M | re.S):
        blocks[m.group(1)] = m.group(0).rstrip("\n")
    return [(s, t) for s, t in statuses], blocks


def failing(text: str, upto: int | None = None) -> set[str]:
    statuses, _ = parse(text)
    return {t for s, t in statuses[:upto] if s in ("FAIL", "ERROR")}


def interrupt_trace(root: Path) -> str:
    """The traceback ci.py prints when a cancel lands inside the reprice loop."""
    def line_of(path: Path, text: str) -> int:
        lines = path.read_text(encoding="utf-8").splitlines()
        hits = [i + 1 for i, l in enumerate(lines) if text in l]
        assert len(hits) == 1, (path, text)
        return hits[0]

    ci_line = line_of(root / "tools" / "ci.py", "tests[tid](result)")
    test_line = line_of(root / "tests" / "test_rates.py", "total += rates.quote(")
    quote_line = line_of(root / "stockroom" / "rates.py", "price = base * t.zone_factor(zone)")
    lib = f"/usr/local/lib/python{sys.version_info.major}.{sys.version_info.minor}/unittest/case.py"
    return "\n".join([
        "Traceback (most recent call last):",
        f'  File "tools/ci.py", line {ci_line}, in child',
        "    tests[tid](result)",
        f'  File "{lib}", line 690, in __call__',
        "    return self.run(*args, **kwds)",
        "           ^^^^^^^^^^^^^^^^^^^^^^^",
        f'  File "{lib}", line 634, in run',
        "    self._callTestMethod(testMethod)",
        f'  File "{lib}", line 589, in _callTestMethod',
        "    if method() is not None:",
        "       ^^^^^^^^",
        f'  File "tests/test_rates.py", line {test_line}, in test_reprice_catalog',
        "    total += rates.quote(s, it.weight_g * (1 + n % 7), 1 + n % 3, it.dims_mm)",
        "             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^",
        f'  File "stockroom/rates.py", line {quote_line}, in quote',
        "    price = base * t.zone_factor(zone) * (1 + t.fuel / 100)",
        "            ~~~~~~~~~~~~~~~~~~~~~~~~~~~^~~~~~~~~~~~~~~~~~~~",
        "KeyboardInterrupt",
    ])


def cancelled(text: str, root: Path) -> str:
    """The output of a run cancelled while CANCEL_TEST was running."""
    statuses, blocks = parse(text)
    ids = [t for _, t in statuses]
    k = ids.index(CANCEL_TEST)
    head = text[: text.index(f"{statuses[k][0]:<6} {CANCEL_TEST}\n")]
    done = statuses[:k]
    out = [head + f"{'ERROR':<6} {CANCEL_TEST}"]
    out += ["\n" + blocks[t] for s, t in done if s in ("FAIL", "ERROR")]
    out.append(f"\n---- ERROR: {CANCEL_TEST}\n" + interrupt_trace(root))
    n = {s: sum(1 for x, _ in done if x == s) for s in ("ok", "FAIL", "ERROR")}
    out.append(f"\nrun cancelled after {k + 1} of {len(ids)} tests: {n['ok']} passed, {n['FAIL']} failed, {n['ERROR'] + 1} errors")
    return "\n".join(out) + "\n"


def log_name(run: dict) -> str:
    return f"{run['now'][:10]}-run-{run['id']}.log"


def run_ids(run: dict) -> list[str]:
    return list(bugs.SHIPPED) + (["D1"] if run["version"] == "2.6.0" else [])


def build(out: Path) -> None:
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"{out} is not empty")
    out.mkdir(parents=True, exist_ok=True)
    copy_tree(HERE / "src", out)
    bugs.apply(out / "stockroom", bugs.SHIPPED)
    runs = json.loads((HERE / "runs.json").read_text(encoding="utf-8"))
    logs = out / "logs" / "ci"
    logs.mkdir(parents=True)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        roots = {}
        for run in runs:
            key = (run["version"], tuple(run_ids(run)))
            if key not in roots:
                roots[key] = project(td / f"p{len(roots)}", run_ids(run), run["version"])
            root = roots[key]
            text = ci(root, run)
            if run.get("cancel"):
                text = cancelled(text, root)
            (logs / log_name(run)).write_text(text, encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    build(Path(sys.argv[1]))
