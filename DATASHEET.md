# Datasheet: CMCA task datasets

Datasheet for the task datasets `datasets/cmca-s` and `datasets/cmca-n`, following the questions of Gebru et al., "Datasheets for Datasets" (arXiv 1803.09010). SPEC sections cited in brackets.

## Motivation

- **Purpose.** Measure how coding-agent harnesses recover when their tool calls fail: task success under seeded faults against a clean baseline, honesty of the self-report, propagation of stale data, and recovery cost (SPEC 1, 5).
- **Creators.** Dan Ávila, with tasks implemented by Claude Code under the owner's review (CLAUDE.md, D-0043).
- **Funding.** Model spend paid by the owner; no external funding.

## Composition

- **Instances.** Each instance is a Harbor task directory: `instruction.md`, `task.toml`, `environment/`, `solution/solve.sh`, `tests/test.sh`, plus a `chaos.toml` sidecar that declares poisonable resources, non-idempotent tools and alternatives (SPEC 10.1).
- **Tracks.**
  - `cmca-s` (service track): tasks over mock MCP services (tickets, inventory, deploy, docs), with shared fixtures in `datasets/cmca-s/fixtures*.py`.
  - `cmca-n` (native track): repository tasks that use read, write, edit, search and shell.
  - `reserve/` holds tasks kept out of the scored set (D-0036).
- **Counts.** The task list of each release is in its methodology and report; the M5 release uses 12 tasks per track (METHODOLOGY 2.5).
- **Labels.** Each task's verifier gives a reward of 1 or 0 from deterministic state checks. There are no human labels.
- **Personal data.** None. Fixtures are synthetic records written for the tasks.
- **Confidentiality.** Every file the agent does not see carries the canary GUID in `datasets/CANARY` so the data can be filtered from training corpora (SPEC 13.2).

## Collection

- Tasks are written as oracle scripts and verifiers, not collected from users or repositories (SPEC 10.3).
- Every task passes per-task validation in CI before it is accepted: lint, build, oracle reward 1 under `clean` and, on the service track, under every fault profile, and `nop` reward 0 (SPEC 10.4, `.github/workflows/task-validation.yml`).

## Preprocessing

None. Trial evidence (trajectories, fault logs, manifests) is produced by runs and stored under `results/`; it is not part of the task datasets.

## Uses

- **Intended.** Evaluating coding-agent harnesses under tool faults with the CMCA fault engine and analysis.
- **Not intended.** Training models. Ranking raw model capability (SPEC 2.2 N1). Adversarial security testing (N4).

## Distribution

- Repository: https://github.com/davila7/chaos-monkey-coding-agents.
- Licenses: code Apache-2.0 (`LICENSE`), data CC BY 4.0 (`LICENSE-DATA`).

## Maintenance

- Maintainer: the repository owner.
- Task bugs: the task-bug issue form; fixes bump the task version and regrade recorded outputs (D-0012, D-0034, SPEC 14).
- Releases are versioned and frozen; changes after a pre-registration tag are recorded as deviations (SPEC 12, 14).
