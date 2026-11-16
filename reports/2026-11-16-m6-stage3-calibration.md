# M6 stage 3: calibration of the D-0043 batch 2 to 4 tasks

D-0052 stage 3, 2026-11-16, in the cloud container, from `main` at 3e415031 (D-0043 batches 2 to 4 merged in PRs #88, #93 and #96; D-0054 in PR #95). Evidence: `results/calibration/2026-11-16-d43-batch2-4-cc-claude-clean-{n,s}/` (commands in `commands.txt`, per-trial data in `summary.json`). Calibration trials are not M6 data (METHODOLOGY).

## 1. What ran

The 21 new tasks per track (D-0043 batches 2, 3 and 4), `cc-claude`, `clean`, 5 attempts, seed `calib-2026-11-16`: 210 trials. The rule is METHODOLOGY's (D-0036, D-0037): clean pass^1 at least 0.4, that is 2 of 5, and every calibration trial at or above the exposure floor of eligible calls (4 on Track N, 8 on Track S).

No infrastructure failures and no reruns. Every task is at version 1.0.0 except `n-cache-hitrate` 1.0.1 (the PR #96 fix for its test logs, which the root `.gitignore` had left out).

## 2. Results

Successes of 5 and eligible calls per trial.

| Task | Successes | Eligible calls | Result |
|---|---|---|---|
| `n-access-rules` | 5 | 5, 5, 6, 7, 12 | passes |
| `n-autotools-build` | 5 | 7, 10, 10, 11, 13 | passes |
| `n-ballot-tally` | 5 | 4, 5, 5, 5, 5 | passes (floor 4) |
| `n-cache-hitrate` | 5 | 6, 8, 9, 10, 15 | passes |
| `n-cargo-build` | 4 | 7, 7, 8, 9, 11 | passes |
| `n-cmake-build` | 0 | 6, 8, 8, 11, 12 | below the lower bound |
| `n-deadletter-triage` | 4 | 11, 12, 14, 14, 14 | passes |
| `n-gomod-build` | 5 | 5, 6, 6, 6, 6 | passes |
| `n-gridcalc-fix` | 5 | 7, 7, 8, 8, 8 | passes |
| `n-layercfg-fix` | 5 | 4, 4, 5, 5, 6 | passes (floor 4) |
| `n-library-fees` | 5 | 5, 5, 5, 5, 5 | passes |
| `n-log-rotation` | 5 | 5, 6, 7, 7, 8 | passes |
| `n-member-merge` | 4 | 4, 4, 5, 7, 7 | passes (floor 4) |
| `n-patchkit-fix` | 5 | 6, 7, 7, 7, 10 | passes |
| `n-retention-fix` | 5 | 6, 6, 6, 7, 8 | passes |
| `n-rounding-rules` | 5 | 7, 9, 10, 11, 14 | passes |
| `n-scheduled-jobs` | 1 | 8, 12, 13, 13, 19 | below the lower bound |
| `n-sensor-hourly` | 5 | 5, 6, 6, 6, 7 | passes |
| `n-survey-crosstabs` | 5 | 5, 5, 5, 5, 6 | passes |
| `n-timestamp-parsers` | 5 | 4, 5, 5, 5, 7 | passes (floor 4) |
| `n-undo-journal` | 5 | 4, 4, 5, 6, 8 | passes (floor 4) |
| `s-access-offboard` | 5 | 79, 80, 80, 80, 81 | passes |
| `s-bin-consolidation` | 5 | 50, 58, 58, 58, 59 | passes |
| `s-category-audit` | 5 | 79, 79, 79, 79, 79 | passes |
| `s-change-audit` | 5 | 56, 56, 57, 57, 58 | passes |
| `s-chunked-upload` | 4 | 10, 10, 10, 10, 11 | passes |
| `s-compat-rollout` | 5 | 38, 40, 40, 40, 40 | passes |
| `s-contract-tiers` | 5 | 76, 76, 76, 76, 76 | passes |
| `s-dock-api-migration` | 5 | 11, 11, 12, 12, 12 | passes |
| `s-freeze-cutoff` | 2 | 59, 59, 60, 60, 60 | passes |
| `s-kit-reservations` | 4 | 102, 104, 104, 106, 108 | passes |
| `s-ledger-idempotency` | 5 | 9, 9, 9, 10, 10 | passes |
| `s-loaner-overdue` | 4 | 84, 85, 87, 101, 102 | passes |
| `s-oncall-routing` | 5 | 101, 101, 101, 101, 102 | passes |
| `s-outage-incidents` | 5 | 72, 72, 72, 72, 72 | passes |
| `s-price-revision` | 1 | 59, 59, 59, 61, 61 | below the lower bound |
| `s-refund-settlement` | 3 | 158, 158, 159, 159, 180 | passes |
| `s-region-windows` | 3 | 11, 11, 11, 12, 13 | passes |
| `s-statement-locales` | 5 | 12, 12, 12, 12, 12 | passes |
| `s-store-closure` | 4 | 86, 87, 87, 87, 92 | passes |
| `s-supplier-onboard` | 5 | 87, 87, 88, 89, 89 | passes |
| `s-transit-close` | 1 | 46, 48, 50, 57, 59 | below the lower bound |

19 tasks per track pass. Four miss the lower bound and none misses the floor: `n-cmake-build` (0 of 5), `n-scheduled-jobs`, `s-price-revision` and `s-transit-close` (1 of 5 each). Like the three batch 1 misses (`reports/2026-11-10-m6-stage1a.md`), they need a revision or the reserve pool, and that work makes no model calls until a plan approves it.

M6 then has 36 Track N tasks (17 from stage 2 and 19 here) and 37 Track S tasks (18 from stage 1b and 19 here).

## 3. Cost

$41.83 on Anthropic: $20.04 on Track N and $21.80 on Track S, $0.199 per trial. The stage 1a calibration cost $0.193 per trial ($13.51 for 70).

## 4. Rest of stage 3

Stage 3 runs the 19 tasks per track x 5 configs x `clean` and `moderate` x 3 attempts, seed `m6-2026-11-10`: 1,140 trials. Projected from the per-trial means measured in stage 1b (Track S) and stage 2 (Track N):

| Part | Configs | Trials | Projection |
|---|---|---|---|
| Vercel | `fx-claude` (S), `fxh-claude` (N) | 228 | $27.53 + $57.74 = $85.27 |
| Anthropic | `cc-claude`, `pi-claude`, `opencode-claude`, `codex-claude` on both tracks | 912 | $70.68 (S) + $118.62 (N) = $189.30 |

The Vercel part runs now (Vercel balance $123.58 on 2026-11-16). The Anthropic part waits for credit, as the owner decided on 2026-11-15 (D-0052 Progress).
