# Methodology

This document describes how the first CMCA results (the M5 pilot, D-0039) are produced. It is frozen with the profiles, configs, tasks and analysis package by the pre-registration tag `pre-m5-YYYY-MM-DD` (SPEC 12). Any change after the tag is recorded as a deviation in the pilot report. SPEC.md is the full specification; this document states what this run does, including where it departs from the SPEC.

## 1. Question

CMCA measures how coding agents behave when their tools fail. A trial runs one agent on one task inside a container while the benchmark makes some tool calls fail, return nothing, return part of their output, or return plausible stale data. The research questions are SPEC section 5: how much success drops under faults (RQ1), which fault families are hardest (RQ2), how much of robustness comes from the harness when the model is fixed (RQ3), how often agents overclaim, propagate stale data or repeat side effects (RQ4), and what recovery costs (RQ5).

## 2. Design

### 2.1 Tracks

- **Track S (service).** Tasks use mock services (tickets, inventory, deploy, docs) over MCP. An MCP proxy in front of the services applies the faults, so every harness receives the same bytes. 12 tasks.
- **Track N (native).** Repository tasks that use the harness's built-in tools (read, write, edit, search, shell). Faults come from an injector loaded through each harness's own hook or extension interface. Rows are compared only within the fixed-model parity set (2.4). 12 tasks.

### 2.2 Configs

All configs use the same model, `claude-sonnet-5-5`, with reasoning effort `medium`, in full autonomy inside the sandbox. Versions are pinned in `configs/<id>.yaml`.

| Config | Harness | Version | Route | Tracks |
|---|---|---|---|---|
| `cc-claude` | Claude Code | 2.1.289 | Anthropic API | S, N |
| `fx-claude` | fx | 0.0.13 | Vercel AI Gateway, pinned to the `anthropic` provider (D-0029) | S |
| `pi-claude` | Pi | 1.0.3 | Anthropic API | S, N |
| `opencode-claude` | OpenCode | 1.18.35 | Anthropic API | S, N |

`codex-gpt` and `agy-gemini` (SPEC 6.2) are not in this run. They join after M3 (D-0039). `fx-claude` has no Track N cell: fx 0.0.13 cannot intercept its built-in tools (V-22), and the board says so.

Recorded differences inside the fixed axis (D-0038, V-24, V-25):

- Pi 1.0.3 run with `--thinking medium` sends a top-level effort `high` and a mid-conversation effort `medium`.
- Pi and OpenCode request thinking with `display: "summarized"`, while Claude Code sends `"omitted"`.
- OpenCode sends one `claude-haiku-5-5` request per run to title the session.
- fx reaches the model through the Vercel AI Gateway instead of the Anthropic API. fx's per-session title request is not pinned to a provider.

These are harness behaviors and are kept as they are. The board shows each difference next to the row.

### 2.3 Profiles

Two profiles, `clean` and `moderate`, frozen in `profiles/`. `moderate`:

- Per-call base rate 0.15, at most 6 applied faults per trial, no warmup.
- Persistence: transient 70%, sticky(2) 30%.
- Type weights (Track S): `deny` 0.10, `err` 0.20, `empty` 0.10, `trunc` 0.15, `falsefail` 0.15, `poison` 0.10, `drift` 0.10, `rate` 0.10. On Track N the weights are renormalized over the harness's parity set.
- Targeted faults (D-0037): in half of the trials, every declared poisonable resource is stale for the whole trial (`stale` persistence). On Track S, in half of the trials, the first call to each declared non-idempotent tool reports a false failure.

`inarg` and `latency` have weight 0 in this run (D-0039 item 2). `inarg` applies only to `fs.read`, `fs.search` and `fs.edit`, and Track N exposure has been almost all `shell` in every pilot. `latency` changes timing, not results. The SPEC 6.4 expectation that the Track N fixed-model parity set includes `inarg` is therefore not met (section 7).

### 2.4 Parity sets

Parity sets come from conformance (`capabilities/<harness>@<version>.json`), never by hand. Claude Code 2.1.289, Pi 1.0.3 and OpenCode 1.18.35 all deliver `deny`, `err`, `empty`, `trunc`, `falsefail` and `poison` on Track N. Claude Code has two parity gaps, `empty` on `fs.write` and `fs.edit`, because its mapper renders a fixed success line (D-0017). The schedule never draws a gap type for that call, so its weight goes to the other eligible types. Track S delivers every service fault type through the proxy for all four configs (V-24, V-25).

### 2.5 Tasks

Track S: `s-change-release` 2.0.0, `s-client-retry` 3.0.0, `s-cycle-count` 2.0.0, `s-damage-claims` 3.0.0, `s-duplicate-merge` 2.0.0, `s-error-catalog` 2.0.0, `s-followups` 2.0.0, `s-incident-rollback` 4.0.0, `s-p1-report` 2.0.0, `s-release-train` 2.0.0, `s-replenish` 2.0.0, `s-shipment-backfill` 2.0.0.

Track N: `n-bisect-regression` 3.0.0, `n-config-threading` 3.0.0, `n-csv-export` 3.0.0, `n-db-build` 2.0.0, `n-invoice-fix` 3.0.0, `n-ledger-fix` 2.0.0, `n-make-build` 2.0.0, `n-port-conflict` 2.0.0, `n-rate-limiter` 3.0.0, `n-shipments-summary` 2.0.0, `n-split-reports` 2.0.0, `n-timesheet-payroll` 3.0.0.

Every task passes per-task CI validation: lint, build, oracle reward 1, `nop` reward 0, and on Track S the oracle under every profile (SPEC 10.4). Every task declares a poisonable resource with a route to the true data (SPEC 7.7). SPEC 10.3 no longer has an upper difficulty bound (D-0036): most tasks pass under `clean` in the calibration runs, so this run separates configs mainly under `moderate`.

### 2.6 Attempts and seed

- n = 3 attempts per task, config and profile (SPEC 20 pilot). Attempt `a` of every config draws from the same schedule function.
- One seed for the run, recorded in the run manifest and the pilot report.
- Run size: Track S 288 trials (12 x 4 x 2 x 3), Track N 216 (12 x 3 x 2 x 3), 504 in all.

## 3. Fault model

SPEC section 7 defines the fault types, the payload catalog (`packages/fault-engine/catalog/v1.json`), capability classes, the deterministic schedule, persistence modes, caps and exemptions. In short:

- The decision for each eligible call is a pure function of seed, task, attempt, capability class, canonical arguments and occurrence count, so it does not depend on timing or call order.
- Targeted faults draw once per trial per declaration.
- Payload text mimics real tooling and never names the experiment. A lint enforces this over the catalog, injector source, file names and environment variables.
- On Track N shell calls, `poison` replaces only the declared lines that the command's output shows. The command itself is never changed.
- Faults never touch `/app/STATUS.json`, `/tests`, `/solution`, `/logs` or the injector directories.

## 4. Metrics

SPEC section 11 defines M1 to M12. The headline is Faulted Success, pass^1 under `moderate`. The board shows it next to:

- Robustness Retention (`moderate` over `clean`)
- pass^3 under `moderate`
- Overclaim rate
- Poison Propagation Rate
- Dollars per success

There is no composite score. With n = 3, pass^3 is the share of tasks where all three attempts succeed.

Fault-event outcomes use the SPEC 11.1 rules with window W = 5 agent steps and the versioned rule files in `python/cmca_analysis/src/cmca_analysis/rules/`: `shell_class_map.yaml` v2, `errors_ack.yaml` v1, `destructive_patterns.yaml` v1, `discovery.yaml` v1, `track_exclusions.yaml` v1.

Delivery is checked against the trajectory:

- `deny`, `err`, `falsefail`: the payload text appears in the result the model saw.
- `empty`: the result is empty or an empty-output rendering.
- `poison`: the declared token appears in the result. A shell call whose output shows none of the declared lines had nothing to replace and is not counted as verifiable.
- `trunc`, `drift`, `rate`: not verifiable from the trajectory.

Cost per trial is the cost the harness reports (Claude Code's total, the sum of Pi's and OpenCode's per-response costs). For fx it is the settled cost read from the AI Gateway (V-16).

## 5. Statistics

- Hierarchical bootstrap: resample tasks with replacement, then attempts within each task. 10,000 replicates, 95% percentile intervals, for every metric on the board.
- Paired permutation test on per-task Faulted Success for every pair of configs on a board, Holm-corrected within the board.
- Rank bands: configs whose 95% intervals for Faulted Success overlap share a band. The site shows bands, not ordinal ranks.
- No pooling across profiles or tracks in the headline.
- The pilot report estimates between-task and within-task variance and the `n` and task counts needed for a minimum detectable difference of 10 points at 80% power (SPEC 12). This run is not sized for that difference.

Analysis package: `cmca-analysis` 0.1.0. `cmca analyze` writes the boards (`site-data/1`) from committed evidence only.

## 6. Exclusions and reruns

- An infrastructure failure is a trial with no verifier reward: model API errors outside injected faults, container crash, or harness crash at startup. It is rerun up to 2 times.
- A trial with an applied parity-set fault whose delivery the trajectory shows as missing is rerun.
- The budget allows 10% reruns. Trials still excluded after reruns are counted on each row.
- A trial that hits the wall-clock limit (30 minutes) is a failure with reason `budget_exhausted`, reported separately.
- Trials where the agent touched injector paths are flagged `injector_discovered` and kept.

## 7. Limitations

- **Two harness families missing.** Codex and Antigravity are not in this run, so there is no native-axis board yet.
- **Track N parity set lacks `inarg`.** `inarg` and `latency` have weight 0, so the set is short of the SPEC 6.4 expectation.
- **Track N exposure is almost all shell.** File-tool faults are rare, and per-call `poison` almost never applies. Stale data on Track N comes from the targeted draw on shell output.
- **fx route and publication.**
  - fx uses the Vercel AI Gateway, a different provider route from the other fixed-axis configs.
  - Vercel's Acceptable Use Policy excludes AI Services from the non-Enterprise benchmark permission, and its API Terms require written permission for performance testing (V-17).
  - The owner chose to publish `fx-claude` rows and to handle the Vercel permission himself (D-0039 progress, 2026-10-19).
- **Effort and thinking differences.** Pi sends effort `high` at the top level. Pi and OpenCode request summarized thinking where Claude Code omits it. The fixed axis is therefore close to identical, not exactly identical.
- **Small n.** Three attempts per cell and 12 tasks per track give wide intervals. Model nondeterminism is not averaged away.
- **Near-ceiling tasks under `clean`.** Most tasks pass under `clean` (D-0036 calibration). Clean pass^1 near 1 leaves Robustness Retention close to Faulted Success, and `clean` differences between configs are small.
- **Cost sources differ.**
  - Claude Code reports its own `total_cost_usd`.
  - Pi and OpenCode report a cost per model response, which Harbor sums. These sums have not been checked against billing (V-16).
  - fx costs come from Gateway records, which can lag (V-16).
- **One host.** All trials run in the cloud container's Docker on Linux x86_64. Harbor's cloud providers are not used.
