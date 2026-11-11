# Methodology

This document describes how the M6 results (D-0051, D-0052) are produced. It is frozen with the profiles, configs, tasks and analysis package by the pre-registration tag `pre-m6-YYYY-MM-DD` (SPEC 12), pushed by the owner before the first M6 trial (stage 1b). Any change after the tag is recorded as a deviation in the release notes with its date. SPEC.md is the full specification; this document states what this run does, including where it departs from the SPEC. The M5 version of this document is the one at tag `pre-m5-2026-10-19` (commit 75993e1).

## 1. Question

CMCA measures how coding agents behave when their tools fail. A trial runs one agent on one task inside a container while the benchmark makes some tool calls fail, return nothing, return part of their output, or return plausible stale data. The research questions are SPEC section 5: how much success drops under faults (RQ1), which fault families are hardest (RQ2), how much of robustness comes from the harness when the model is fixed (RQ3), how often agents overclaim, propagate stale data or repeat side effects (RQ4), and what recovery costs (RQ5).

## 2. Design

### 2.1 Tracks

- **Track S (service).** Tasks use mock services (tickets, inventory, deploy, docs) over MCP. An MCP proxy in front of the services applies the faults, so every harness receives the same bytes.
- **Track N (native).** Repository tasks that use the harness's built-in tools (read, write, edit, search, shell). Faults come from an injector loaded through each harness's own hook or extension interface. Rows are compared only within the fixed-model parity set (2.4).

### 2.2 Configs

All configs use the same model, `claude-sonnet-5-5`, with reasoning effort `medium`, in full autonomy inside the sandbox. Versions are pinned in `configs/<id>.yaml`.

| Config | Harness | Version | Route | Tracks |
|---|---|---|---|---|
| `cc-claude` | Claude Code | 2.1.289 | Anthropic API | S, N |
| `fx-claude` | fx | 0.0.13 | Vercel AI Gateway, pinned to the `anthropic` provider (D-0029) | S |
| `fxh-claude` | fxh, fork of fx 0.0.13 with tool hooks (D-0040) | 0.0.13-h1 | Vercel AI Gateway, as `fx-claude` | N |
| `pi-claude` | Pi | 1.0.3 | Anthropic API | S, N |
| `opencode-claude` | OpenCode | 1.18.35 | Anthropic API | S, N |
| `codex-claude` | Codex CLI | 0.163.0 | Anthropic API through `packages/responses-bridge` (D-0044) | S, N |

`muse-spark`, `codex-gpt` and `agy-gemini` are not in M6 (D-0051 items 1 and 2). fx 0.0.13 cannot intercept its built-in tools (V-22), so the fx row on Track N is `fxh-claude`; the board says so.

Recorded differences inside the fixed axis (D-0038, D-0044, V-24, V-25, V-28):

- Pi 1.0.3 run with `--thinking medium` sends a top-level effort `high` and a mid-conversation effort `medium`.
- Pi and OpenCode request thinking with `display: "summarized"`, while Claude Code sends `"omitted"`.
- OpenCode sends one `claude-haiku-5-5` request per run to title the session.
- fx and fxh reach the model through the Vercel AI Gateway instead of the Anthropic API. fx's per-session title request is not pinned to a provider.
- Codex speaks only the Responses API; the bridge translates each request to the Messages API. Hosted web search and sub-agents are off, and MCP tools are offered up front. Codex has no read, search or list tool, so `fs.read`, `fs.search` and `fs.list` faults never apply to it.

These are harness behaviors and are kept as they are. The board shows each difference next to the row.

### 2.3 Profiles

Leaderboard profiles `clean` and `moderate`; curve profiles `light` and `heavy` (D-0052 item 1). All four are frozen in `profiles/`.

- `light`: per-call base rate 0.05, at most 3 applied faults per trial, all transient, no targeted faults.
- `moderate`: per-call base rate 0.15, at most 6 applied faults per trial, transient 70% and sticky(2) 30%. Targeted faults (D-0037): in half of the trials every declared poisonable resource is stale for the whole trial; on Track S, in half of the trials the first call to each declared non-idempotent tool reports a false failure.
- `heavy`: per-call base rate 0.30, at most 10 applied faults per trial, transient 50%, sticky(2) 35%, outage 15% (window 3). Targeted poison and false failure in every trial.
- Type weights in every faulted profile (Track S): `deny` 0.10, `err` 0.20, `empty` 0.10, `trunc` 0.15, `falsefail` 0.15, `poison` 0.10, `drift` 0.10, `rate` 0.10. On Track N the weights are renormalized over the harness's parity set. No warmup.

`inarg` and `latency` have weight 0 (D-0039 item 2), so the SPEC 6.4 expectation that the Track N fixed-model parity set includes `inarg` is not met (section 7).

### 2.4 Parity sets

Parity sets come from conformance (`capabilities/<harness>@<version>.json`), never by hand. Claude Code 2.1.289, Pi 1.0.3, OpenCode 1.18.35, fxh 0.0.13-h1 and Codex 0.163.0 deliver `deny`, `err`, `empty`, `trunc`, `falsefail` and `poison` on Track N for the tool classes each harness has. Claude Code has two parity gaps, `empty` on `fs.write` and `fs.edit` (D-0017). The schedule never draws a gap type for that call, so its weight goes to the other eligible types. Track S delivers every service fault type through the proxy for all five Track S configs.

### 2.5 Tasks

A task enters M6 only after per-task CI validation (lint, build, oracle reward 1, `nop` reward 0, and on Track S the oracle under every profile, SPEC 10.4) and pilot calibration with `cc-claude` under `clean`, 5 attempts: clean pass^1 at least 0.4 and the exposure floor in the calibration trials (SPEC 10.3, D-0036, D-0037: 8 eligible calls on Track S, 4 on Track N). Every task declares a poisonable resource with a route to the true data (SPEC 7.7).

Track S, stage 1b (18 tasks):

- M5 tasks (calibrated in D-0034 to D-0036): `s-change-release` 2.0.0, `s-client-retry` 3.0.0, `s-cycle-count` 2.0.0, `s-damage-claims` 3.0.0, `s-duplicate-merge` 2.0.0, `s-error-catalog` 2.0.0, `s-followups` 2.0.0, `s-incident-rollback` 4.0.0, `s-p1-report` 2.0.0, `s-release-train` 2.0.0, `s-replenish` 2.0.0, `s-shipment-backfill` 2.0.0.
- D-0043 batch 1, calibrated in `results/calibration/2026-11-10-batch1-cc-claude-clean-s/`: `s-canary-promote` 1.0.0, `s-hotfix-backport` 1.0.0, `s-lot-recall` 1.0.0, `s-pagination-client` 1.0.0, `s-sla-breach` 1.0.0, `s-warranty-returns` 1.0.0.
- `s-webhook-signature` 1.0.0 passes the lower bound (5 of 5) but not the floor (5 to 6 eligible calls), so it is not in M6 as shipped.

Track N (stage 2) and the 21 new tasks per track (stage 3) are listed in the release notes with the date each set is fixed. Batch 1 calibration on Track N (`results/calibration/2026-11-10-batch1-cc-claude-clean-n/`): `n-flaky-tests`, `n-recurrence-fix`, `n-transit-boards`, `n-units-fix` and `n-wheel-build` pass; `n-plugin-registry` and `n-semver-ranges` (0 of 5) do not.

### 2.6 Attempts, seed and size

- n = 3 attempts per task, config and profile on the leaderboard profiles; n = 2 on the curve profiles, on 20 tasks per track stratified by category (D-0052 item 1; SPEC 20 says 3). Attempt `a` of every config draws from the same schedule function.
- One seed for M6, recorded in the run manifest and the release notes.
- Stage 1b: Track S, 18 tasks x 5 configs x 2 profiles x 3 attempts = 540 trials.
- The stages, their caps and their stop rules are D-0052 items 2 and 4. Stage 1a trials (calibration and cost gate) are not M6 data.

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

There is no composite score. With n = 3, pass^3 is the share of tasks where all three attempts succeed. The degradation curve per config is pass^1 under `clean`, `light`, `moderate` and `heavy` on the curve task subset.

Fault-event outcomes use the SPEC 11.1 rules with window W = 5 agent steps and the versioned rule files in `python/cmca_analysis/src/cmca_analysis/rules/`: `shell_class_map.yaml` v2, `errors_ack.yaml` v1, `destructive_patterns.yaml` v1, `discovery.yaml` v1, `track_exclusions.yaml` v1.

Delivery is checked against the trajectory:

- `deny`, `err`, `falsefail`: the payload text appears in the result the model saw.
- `empty`: the result is empty or an empty-output rendering.
- `poison`: the declared token appears in the result. A shell call whose output shows none of the declared lines had nothing to replace and is not counted as verifiable.
- `trunc`, `drift`, `rate`: not verifiable from the trajectory.

Cost per trial is the cost the harness reports: Claude Code's total, the sum of Pi's and OpenCode's per-response costs, and for fx and fxh the settled cost read from the AI Gateway (V-16). For `codex-claude` it is the bridge usage log priced at Anthropic list prices (D-0045).

## 5. Statistics

- Hierarchical bootstrap: resample tasks with replacement, then attempts within each task. 10,000 replicates, 95% percentile intervals, for every metric on the board.
- Paired permutation test on per-task Faulted Success for every pair of configs on a board, Holm-corrected within the board.
- Rank bands: configs whose 95% intervals for Faulted Success overlap share a band. The site shows bands, not ordinal ranks.
- No pooling across profiles or tracks in the headline.
- The release notes report between-task and within-task variance and the minimum detectable difference at 80% power for the run as sized (SPEC 12).

Analysis package: `cmca-analysis` 0.1.0 at the tagged commit. `cmca analyze` writes the boards (`site-data/1`) from committed evidence only. Boards are published once, from one release, after the last stage (D-0052 consequences).

## 6. Exclusions and reruns

- An infrastructure failure is a trial with no verifier reward: model API errors outside injected faults, container crash, image build failure, or harness crash at startup. It is rerun up to 2 times.
- A trial with an applied parity-set fault whose delivery the trajectory shows as missing is rerun.
- The budget allows 10% reruns. Trials still excluded after reruns are counted on each row.
- A trial that hits the agent time limit is a failure with reason `budget_exhausted`, reported separately. Each task file sets the agent `timeout_sec`: 1800 or 3600 depending on the task. M5's text said 30 minutes for every task, which was wrong (M5 report correction).
- Trials where the agent touched injector paths are flagged `injector_discovered` and kept.
- A stage stops and goes to the owner if infrastructure failures pass 3% of its trials, fault delivery falls below 99% on any config, or the observed cost per trial passes the estimate by more than 25% (D-0052 item 4).

## 7. Limitations

- **Antigravity missing.** No native-axis board.
- **Track N parity set lacks `inarg`.** `inarg` and `latency` have weight 0.
- **Track N exposure is almost all shell.** File-tool faults are rare, and per-call `poison` almost never applies. Stale data on Track N comes from the targeted draw on shell output.
- **Codex Track N delivery.** Codex fires `PostToolUse` for a command still running when `exec_command` returns only when the process ends, or never (V-02 addendum). Stage 2 does not start until the D-0051 item 3 plan closes this or declares it as a gap.
- **fx route and publication.**
  - fx and fxh use the Vercel AI Gateway, a different provider route from the other fixed-axis configs.
  - Vercel's Acceptable Use Policy excludes AI Services from the non-Enterprise benchmark permission, and its API Terms require written permission for performance testing (V-17). The owner publishes the fx rows and handles the Vercel permission himself.
- **Effort and thinking differences.** Pi sends effort `high` at the top level. Pi and OpenCode request summarized thinking where Claude Code omits it. The fixed axis is therefore close to identical, not exactly identical.
- **Staged task suite.** Tasks join in stages (D-0052): Track S first, Track N after the codex plan, then 21 new tasks per track. Every stage uses the same profiles, configs and seed.
- **Near-ceiling tasks under `clean`.** Most tasks pass under `clean`, so configs separate mainly under `moderate` and `heavy`.
- **Cost sources differ.**
  - Claude Code reports its own `total_cost_usd`.
  - Pi and OpenCode report a cost per model response, which Harbor sums. These sums have not been checked against billing (V-16).
  - fx and fxh costs come from Gateway records, which can lag (V-16).
  - Codex costs are computed from the bridge's token counts at list prices.
- **One host.** All trials run in the cloud container's Docker on Linux x86_64. Harbor's cloud providers are not used.
