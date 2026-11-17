# M6 stage 3, Anthropic part: cc-claude, pi-claude, opencode-claude and codex-claude on the new tasks

D-0052 stage 3, 2026-11-17, in the cloud container, from `main` at e2c2cc66. This is the second part of the stage split decided by the owner on 2026-11-15 (D-0052 Progress). The Vercel part is in `reports/2026-11-16-m6-stage3-vercel.md`. With this part, stage 3 is complete. Evidence: `results/pilot/2026-11-17-m6-s3a-s/` (Track S) and `results/pilot/2026-11-17-m6-s3a-n/` (Track N), each with `commands.txt` and `summary.json`. The success counts below are raw counts for the stage check, not board metrics.

## 1. What ran

The 19 tasks per track that passed the stage 3 calibration (`reports/2026-11-16-m6-stage3-calibration.md`), `clean` and `moderate`, 3 attempts, seed `m6-2026-11-10`: 114 trials per config and track, 912 in total.

The owner asked on 2026-11-17 to finish within the Anthropic balance loaded that day ($214.55). Track S ran first, then Track N attempts 0 and 1. Track N cost less than projected, so attempt 2 also fit in the balance and ran from 12:19 UTC.

- No archived trial is an infrastructure failure (every one has a verifier reward).
- One delivery rerun (METHODOLOGY 6). In `codex-claude` `moderate` attempt 2 of `n-cache-hitrate`, the injector applied an `empty` fault to a command that Codex then rejected by its own policy ("rm -f style commands are not permitted"). The model saw the rejection, not the empty output. The rerun delivered all of its verifiable faults. Both trials are archived; the tables below count the rerun in place of the original, and the cost totals include both.

The container disk filled at the start of the run (02:57 to 03:17 UTC): earlier Track N plans had left 4.7 GB of generated repositories in `/tmp/tt-gen-*`, and the docker build cache held 4.5 GB. Trials failed with `No space left on device`. The 6 affected jobs were moved to `jobs/m6/stage3/_diskfull/` (not archived) and rerun from scratch after the disk was freed. Their measured cost is $1.32; the spend of the trials cut in flight is in no `result.json` and is not measured. Since then the plan command removes its generated repositories when it exits (`cmca_harbor.conformance`), and the runner starts a job only with enough free disk.

## 2. Stop rules (D-0052 item 4)

| Rule | Observed | Status |
|---|---|---|
| Infrastructure failures at most 3% | 0 of 912 archived trials (the disk-full jobs above were rerun before archiving) | Met |
| Fault delivery at least 99% on every config | 100% on every config and track after the one delivery rerun (section 3) | Met |
| Cost per trial at most 25% above the estimate | $0.194 per trial (913 trials with the rerun) against $0.208 projected for this part (section 4) | Met |

## 3. Raw outcomes and delivery

Successes over 57 trials per config, track and profile (19 tasks x 3 attempts).

| Config | Track | `clean` | `moderate` | Faults applied | Verifiable | Delivered |
|---|---|---|---|---|---|---|
| `cc-claude` | S | 51 | 37 | 284 | 206 | 206 |
| `pi-claude` | S | 52 | 35 | 283 | 204 | 204 |
| `opencode-claude` | S | 53 | 37 | 288 | 207 | 207 |
| `codex-claude` | S | 52 | 38 | 285 | 204 | 204 |
| `cc-claude` | N | 52 | 43 | 99 | 73 | 73 |
| `pi-claude` | N | 54 | 47 | 95 | 74 | 74 |
| `opencode-claude` | N | 55 | 47 | 110 | 87 | 87 |
| `codex-claude` | N | 54 | 46 | 132 | 90 | 90 |

Verifiable excludes `trunc`, `drift` and `rate`, which the trajectory cannot confirm. Two `codex-claude` Track N faults are undeliverable and not counted as applied: commands that outlived their yield (D-0053), one logged by the injector and one found by the analysis.

Delivery check fix. The first Track N summary showed one `cc-claude` fault as not delivered (`n-layercfg-fix`, `moderate`, attempt 0: a `deny` on one of 10 parallel `Read` calls in one step). The trajectory shows the denial on `errors.py`. The summary had paired the fault with a sibling `Read` by position, because parallel calls reach the injector in completion order, and the sibling that showed the denial was held by a `trunc` fault, which cannot be verified. `cmca_analysis.trials` now moves a fault that its position paired with the wrong call to the call in its step that shows it, and swaps with a sibling held by a fault that is not shown as delivered there. `cmca_analysis.reconcile` already looked for a free sibling and now applies the same swap. With the fix, regenerating the earlier stage summaries changes one trial: the stage 2 `cc-claude` `n-split-reports` fault that `reports/2026-11-12-m6-stage2.md` section 5 already names as a check artifact now reads as delivered (Track N `moderate` 537 of 544 instead of 536; `results/pilot/2026-11-12-m6-n/summary.json` regenerated). The other stage summaries are unchanged.

## 4. Cost

| Config | Track | Total | Mean per trial, `clean` | Mean per trial, `moderate` |
|---|---|---|---|---|
| `cc-claude` | S | $26.78 | $0.215 | $0.255 |
| `pi-claude` | S | $21.44 | $0.175 | $0.202 |
| `opencode-claude` | S | $21.95 | $0.178 | $0.207 |
| `codex-claude` | S | $24.53 | $0.201 | $0.229 |
| `cc-claude` | N | $23.10 | $0.186 | $0.219 |
| `pi-claude` | N | $18.00 | $0.147 | $0.168 |
| `opencode-claude` | N | $17.48 | $0.144 | $0.163 |
| `codex-claude` | N | $24.29 | $0.190 | $0.232 |

The `codex-claude` Track N total includes the original trial and the delivery rerun; the means count the rerun in place of the original.

Measured total $177.57 ($94.70 Track S, $82.87 Track N), plus $1.32 for the disk-full jobs. The calibration report projected $189.30 for this part ($70.68 Track S, $118.62 Track N). By track the projection missed in both directions, as it did for the Vercel part: Track S ran 34% over its stage 1b means on these tasks, and Track N ran 30% under its stage 2 means.

## 5. Next

- Stage 4 (curve profiles `light` and `heavy`, D-0052 item 1). It needs owner credit.
- The seven tasks that missed calibration (three from batch 1, four from batches 2 to 4) need a revision or the reserve pool, with a plan before any model call.
