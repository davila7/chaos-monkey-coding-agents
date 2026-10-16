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

## Task bugs

Report a task that is unsolvable, solvable without doing the work, or graded wrongly with the "Task bug" issue form. Triage:

1. A maintainer reproduces the report with the oracle, `nop`, or the trial cited in the issue, and labels it `task-bug` once confirmed.
2. The fix goes in a pull request that bumps the task version by the rule above and names the issue.
3. `CHANGELOG.md` records the fix with the task id and both versions.

Security or safety findings follow the private disclosure route in SPEC 15.3, not a public issue.
