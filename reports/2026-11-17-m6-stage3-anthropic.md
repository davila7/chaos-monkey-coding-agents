# M6 stage 3, Anthropic part: cc-claude, pi-claude, opencode-claude and codex-claude on the new tasks

D-0052 stage 3, 2026-11-17, in the cloud container, from `main` at e2c2cc66. This is the second part of the stage split decided by the owner on 2026-11-15 (D-0052 Progress). The Vercel part is in `reports/2026-11-16-m6-stage3-vercel.md`. Evidence: `results/pilot/2026-11-17-m6-s3a-s/` (Track S) and `results/pilot/2026-11-17-m6-s3a-n/` (Track N), each with `commands.txt` and `summary.json`. The success counts below are raw counts for the stage check, not board metrics.

## 1. What ran

The 19 tasks per track that passed the stage 3 calibration (`reports/2026-11-16-m6-stage3-calibration.md`), `clean` and `moderate`, seed `m6-2026-11-10`:

- Track S: 3 attempts, 114 trials per config, 456 in total.
- Track N: attempts 0 and 1, 76 trials per config, 304 in total. The owner decided on 2026-11-17 to finish within the Anthropic balance loaded that day ($214.55), so Track N attempt 2 (152 trials) waits for credit (deviation, D-0052 Progress). Every config has the same attempts, so the part stays balanced across configs.

No archived trial is an infrastructure failure (every one has a verifier reward), and no trial needed a delivery rerun.

The container disk filled at the start of the run (02:57 to 03:17 UTC): earlier Track N plans had left 4.7 GB of generated repositories in `/tmp/tt-gen-*`, and the docker build cache held 4.5 GB. Trials failed with `No space left on device`. The 6 affected jobs were moved to `jobs/m6/stage3/_diskfull/` (not archived) and rerun from scratch after the disk was freed. Their measured cost is $1.32; the spend of the trials cut in flight is in no `result.json` and is not measured. Since then the plan command removes its generated repositories when it exits (`cmca_harbor.conformance`), and the runner starts a job only with enough free disk.

## 2. Stop rules (D-0052 item 4)

| Rule | Observed | Status |
|---|---|---|
| Infrastructure failures at most 3% | 0 of 760 archived trials (the disk-full jobs above were rerun before archiving) | Met |
| Fault delivery at least 99% on every config | 100% on every config and track (section 3) | Met |
| Cost per trial at most 25% above the estimate | $0.196 per trial against $0.197 projected for this part (section 4) | Met |

## 3. Raw outcomes and delivery

Successes per config and profile. Track S has 57 trials per cell (19 tasks x 3 attempts), Track N 38 (19 tasks x 2 attempts).

| Config | Track | `clean` | `moderate` | Faults applied | Verifiable | Delivered |
|---|---|---|---|---|---|---|
| `cc-claude` | S | 51/57 | 37/57 | 284 | 206 | 206 |
| `pi-claude` | S | 52/57 | 35/57 | 283 | 204 | 204 |
| `opencode-claude` | S | 53/57 | 37/57 | 288 | 207 | 207 |
| `codex-claude` | S | 52/57 | 38/57 | 285 | 204 | 204 |
| `cc-claude` | N | 35/38 | 28/38 | 64 | 46 | 46 |
| `pi-claude` | N | 35/38 | 32/38 | 71 | 55 | 55 |
| `opencode-claude` | N | 38/38 | 32/38 | 72 | 57 | 57 |
| `codex-claude` | N | 36/38 | 30/38 | 89 | 62 | 62 |

Verifiable excludes `trunc`, `drift` and `rate`, which the trajectory cannot confirm. One `codex-claude` Track N fault was logged by the injector as undeliverable (a command that outlived its yield, D-0053) and is not counted as applied.

Delivery check fix. The first summary showed one `cc-claude` Track N fault as not delivered (`n-layercfg-fix`, `moderate`, attempt 0: a `deny` on one of 10 parallel `Read` calls in one step). The trajectory shows the denial on `errors.py`. The summary had paired the fault with a sibling `Read` by position, because parallel calls reach the injector in completion order, and the sibling that showed the denial was held by a `trunc` fault, which cannot be verified. `cmca_analysis.trials` now moves a fault that its position paired with the wrong call to the call in its step that shows it, and swaps with a sibling held by a fault that is not shown as delivered there. `cmca_analysis.reconcile` already looked for a free sibling and now applies the same swap. With the fix, regenerating the earlier stage summaries changes one trial: the stage 2 `cc-claude` `n-split-reports` fault that `reports/2026-11-12-m6-stage2.md` section 5 already names as a check artifact now reads as delivered (Track N `moderate` 537 of 544 instead of 536; `results/pilot/2026-11-12-m6-n/summary.json` regenerated). The other stage summaries are unchanged.

## 4. Cost

| Config | Track | Total | Mean per trial, `clean` | Mean per trial, `moderate` |
|---|---|---|---|---|
| `cc-claude` | S | $26.78 | $0.215 | $0.255 |
| `pi-claude` | S | $21.44 | $0.175 | $0.202 |
| `opencode-claude` | S | $21.95 | $0.178 | $0.207 |
| `codex-claude` | S | $24.53 | $0.201 | $0.229 |
| `cc-claude` | N | $14.96 | $0.182 | $0.212 |
| `pi-claude` | N | $12.24 | $0.149 | $0.173 |
| `opencode-claude` | N | $11.32 | $0.142 | $0.155 |
| `codex-claude` | N | $15.36 | $0.189 | $0.215 |

Measured total $148.58 ($94.70 Track S, $53.88 Track N), plus $1.32 for the disk-full jobs. The projection for this part was $70.68 for Track S and $79.08 for Track N attempts 0 and 1 (two thirds of the $118.62 for 3 attempts in the calibration report): $149.76 for 760 trials. By track the projection missed in both directions, as it did for the Vercel part. Track S ran 34% over its stage 1b means on these tasks, and Track N ran 32% under its stage 2 means.

## 5. Next

- Track N attempt 2 for the four configs: 152 trials, about $27 at this part's Track N means. It waits for credit.
- Stage 4 (curve profiles `light` and `heavy`, D-0052 item 1).
- The seven tasks that missed calibration (three from batch 1, four from batches 2 to 4) need a revision or the reserve pool, with a plan before any model call.
