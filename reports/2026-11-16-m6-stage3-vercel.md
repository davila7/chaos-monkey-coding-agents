# M6 stage 3, Vercel part: fx-claude and fxh-claude on the new tasks

D-0052 stage 3, 2026-11-16, in the cloud container, from `main` at 3e415031. This is the first part of the stage split decided by the owner on 2026-11-15 (D-0052 Progress): the two configs billed through the Vercel AI Gateway run now, the four Anthropic configs later. Evidence: `results/pilot/2026-11-16-m6-s3-s/` (`fx-claude`) and `results/pilot/2026-11-16-m6-s3-n/` (`fxh-claude`), each with `commands.txt` and `summary.json`. The success counts below are raw counts for the stage check, not board metrics.

## 1. What ran

The 19 tasks per track that passed the stage 3 calibration (`reports/2026-11-16-m6-stage3-calibration.md`) x `clean` and `moderate` x 3 attempts, seed `m6-2026-11-10`: 114 `fx-claude` trials on Track S and 114 `fxh-claude` trials on Track N, 228 in total.

- No infrastructure failures (no trial without a verifier reward) and no delivery reruns.
- Five `fxh-claude` trials have no cost in `result.json`: four whose fx usage snapshot had nothing pending and one with 2 pending generations. Their cost is in `settled-usage.json` (from the snapshot, and for the pending generations from `GET /v1/generation`), which `cmca_analysis analyze` reads (D-0030). `summary.json` shows them without cost.

## 2. Stop rules (D-0052 item 4)

| Rule | Observed | Status |
|---|---|---|
| Infrastructure failures at most 3% | 0 of 228 | Met |
| Fault delivery at least 99% on every config | `fx-claude` 208 of 208 verifiable, `fxh-claude` 152 of 152 | Met |
| Cost per trial at most 25% above the estimate | Vercel $0.354 per trial against $0.374 projected in the calibration report (5% under) | Met |

## 3. Raw outcomes and delivery

Successes over 57 trials per config and profile (19 tasks x 3 attempts).

| Config | `clean` | `moderate` | Faults applied | Verifiable | Delivered |
|---|---|---|---|---|---|
| `fx-claude` (Track S) | 55 | 40 | 291 | 208 | 208 |
| `fxh-claude` (Track N) | 53 | 49 | 182 | 152 | 152 |

Verifiable excludes `trunc`, `drift` and `rate`, which the trajectory cannot confirm. No applied fault was logged as undeliverable.

## 4. Cost

| Config | Total | Mean per trial, `clean` | Mean per trial, `moderate` | Projection |
|---|---|---|---|---|
| `fx-claude` | $39.17 | $0.328 | $0.359 | $27.53 |
| `fxh-claude` | $41.44 | $0.345 | $0.382 | $57.74 |

Vercel total $80.61 against the $85.27 projection; the gateway balance fell from $123.58 to $42.94 over the run ($80.64). By config the projection missed in both directions: `fx-claude` ran 42% over its stage 1b means on these tasks, which need more calls (up to 180 eligible calls in calibration), and `fxh-claude` ran 28% under its stage 2 means.

## 5. Next

The four Anthropic configs (`cc-claude`, `pi-claude`, `opencode-claude`, `codex-claude`) on the same 19 tasks per track: 912 trials, projected $189.30. They run when the owner has the credit.
