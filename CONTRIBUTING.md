# Contributing

SPEC.md is the source of truth. A change that departs from it starts as an entry in DECISIONS.md and lands only after the owner approves it.

## Checks

A pull request passes the CI jobs before review:

    pnpm install --frozen-lockfile && pnpm build && pnpm typecheck && pnpm test && pnpm lint
    uv sync --all-packages --locked && uv run pytest

## Task versions

Every `task.toml` carries `version = "MAJOR.MINOR.PATCH"` in its `[task]` table, and any change to a task's directory bumps it (D-0012). CI runs `cmca task-bump --base <base branch>` on pull requests.

- PATCH: nothing the agent sees or the verifier checks changes (metadata, typos in files the agent never sees). Existing results stay valid.
- MINOR: the verifier changes and the agent environment does not. Recorded agent outputs are re-graded.
- MAJOR: anything the agent sees or experiences changes: `instruction.md`, `environment/`, mock service behavior, the task's `chaos.toml`, or the catalog, profiles or injector build it runs with. Trials are rerun.

## Adding a harness

A harness joins the boards only after it passes conformance on a pinned version (SPEC 9.6). Codex (D-0044) is the most recent example to follow.

1. Open a "Harness request" issue. Pin a stable release at least 7 days old.
2. Write the plan as a DECISIONS.md entry and wait for the owner's approval (CLAUDE.md rule 1). Read the harness's official hook or plugin documentation, test it against the pinned binary in a container, and record both in `docs/verification/V-xx.md`. When they disagree, observed behavior wins.
3. Track N: add `packages/injector-<harness>`, a TypeScript adapter from the harness's hook payload to `tt-decide` (see `packages/injector-pi`), with tests. A harness without an interception point for its built-in tools can still join Track S (V-22).
4. Add a Harbor agent in `python/cmca_harbor/<harness>.py` that subclasses Harbor's installed agent with `TtAgentMixin`, and export it from `cmca_harbor/__init__.py`.
5. Add `configs/<harness>-claude.yaml` (`schema: tt-config/1`): pinned version, `harbor_agent`, model `claude-sonnet-5-5`, reasoning effort and autonomy setting.
6. Run conformance with `python -m cmca_harbor.conformance plan` and `report`. The report writes `capabilities/<harness>@<version>.json`; record each parity gap with `--gap` and its reason. Conformance probes are the only model calls allowed without an approved cost estimate (CLAUDE.md rule 5).
7. Calibration and board runs need an approved cost estimate (SPEC 20). Results enter a release only through `cmca_analysis analyze`.

## Tasks

Task format and validation rules are in SPEC 10. Each new or changed task passes `python -m cmca_harbor.validate` (oracle scores 1, `nop` scores 0, and on Track S the oracle passes under every fault profile) and the review checklist in `docs/review-checklist.md`. The `task-validation` workflow runs the same checks on pull requests.

## Task bugs

Report a task that is unsolvable, solvable without doing the work, or graded wrongly with the "Task bug" issue form. Triage:

1. A maintainer reproduces the report with the oracle, `nop`, or the trial cited in the issue, and labels it `task-bug` once confirmed.
2. The fix goes in a pull request that bumps the task version by the rule above and names the issue.
3. `CHANGELOG.md` records the fix with the task id and both versions.

Security or safety findings follow the private disclosure route in SPEC 15.3, not a public issue.
