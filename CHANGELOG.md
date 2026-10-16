# Changelog

## Unreleased

- M0 foundations: fault engine, catalog v1, profiles, schemas, `tt-decide`, banned-word and canary lint, event log validation, CI, verification register.
- M1 (in progress): native injectors for Claude Code 2.1.289, Pi 1.0.3 and OpenCode 1.18.35 (OpenCode on the v1 hooks, D-0019); conformance runner (D-0020) and capability files with parity gaps (D-0017); Harbor custom agents.
- Track N: 3 pilot tasks (D-0021), recalibrated under D-0023, D-0024 and D-0026; trial planner and run summary.
- Runs: smoke run 2026-10-11 and clean pilots 2026-10-12, 2026-10-13 and 2026-10-14 with `cc-claude`, evidence in `results/`.
- Results site and build log (D-0016, D-0018, D-0025).
- M4 analysis (D-0032): ingest, validation, reconciliation, SPEC 11.1 and 11.2 classification, metrics M1 to M12, hierarchical bootstrap, paired permutation tests with Holm correction, rank bands, board summaries and `site-data/1` output, `cmca analyze`; V-16 closed for `cc-claude` and `fx-claude`. Site: every smoke run listed, unified All tracks view (D-0031).
- SPEC 11.1 shell retries compare the command's class or program (D-0033). V-22 closed: fx 0.0.13 has no interception point for built-in tools.
- Task versions (D-0012, D-0034): `version` in every `task.toml`, lint checks for the version, `chaos.toml` schema and completion contract, `cmca task-bump` in CI, task-bug issue form and triage in `CONTRIBUTING.md`.
- Per-task validation without a model (D-0034): `cmca_harbor.validate` and the `task-validation` workflow (oracle under every profile on Track S, `nop`), ABC review checklist. Mock services `inventory`, `deploy` and `docs` (SPEC 9.2).
- Track S: nine new tasks on the `inventory`, `deploy` and `docs` services, two of them across several services (D-0034 item 5); `deploy` gains `list_services` and a `status` history limit.
- Track N: nine new tasks, two per category with the existing three (D-0034 item 5).
- Calibration round 1 (D-0034 item 6): 24 tasks, `cc-claude` clean, 5 attempts each, evidence in `results/calibration/`.
