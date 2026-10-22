# fxh Track N pilot report

Run: D-0040 item 9, config `fxh-claude` (fxh 0.0.13-h1, the fork of fx 0.0.13 with tool hooks), seed `m5-2026-10-19`, the M5 Track N task set, profiles `clean` and `moderate`, n = 3. Trials ran 2026-10-21 19:18 UTC to 2026-10-22 00:52 UTC in the cloud container's Docker.

This is a pilot. `fxh-claude` is not part of M5 (D-0040 item 8): `results/2026-10-20-m5` and the site's `results.json` do not change. It joins the boards in M6 under a new pre-registration.

Evidence: `results/pilot/2026-10-21-fxh-n` (commands in `commands.txt`, per-run summary in `summary.json`). The comparison board in `results/pilot/2026-10-21-fxh-n/analysis/track-n-fixed` was written by `python -m cmca_analysis analyze` from this evidence plus `results/pilot/2026-10-19-m5-n`. Its `cc-claude`, `pi-claude` and `opencode-claude` rows match `results/2026-10-20-m5/track-n-fixed`. Cost gate: `results/smoke/2026-10-21-track-n-fxh`. Every number below comes from those files.

## 1. Results

Faulted Success is pass^1 under `moderate`. Intervals are 95% hierarchical bootstrap intervals, 10,000 replicates. Cost is the harness-reported cost over both profiles (V-16); `fxh-claude` is billed through the Vercel AI Gateway, the other three through the Anthropic API.

| Config | clean pass^1 | Faulted Success | Retention | pass^3 moderate | Overclaim | Poison propagation | $ per success (moderate) | Cost |
|---|---|---|---|---|---|---|---|---|
| `cc-claude` | 0.944 | 0.833 [0.64, 0.97] | 0.882 [0.67, 1.03] | not computed | 0.833 [0.00, 1.00] | 0.222 [0.00, 0.67] | $0.466 | $26.28 |
| `fxh-claude` | 0.917 | 0.806 [0.61, 0.97] | 0.879 [0.66, 1.03] | 0.583 [0.42, 0.92] | 1.000 [1.00, 1.00] | 0.188 [0.00, 0.50] | $0.731 | $38.97 |
| `opencode-claude` | 0.944 | 0.806 [0.64, 0.94] | 0.853 [0.66, 1.00] | 0.500 [0.33, 0.92] | 0.667 [0.00, 1.00] | 0.185 [0.00, 0.65] | $0.353 | $20.67 |
| `pi-claude` | 0.889 | 0.722 [0.50, 0.92] | 0.781 [0.54, 0.97] | 0.500 [0.33, 0.83] | 0.900 [0.58, 1.00] | 0.130 [0.00, 0.53] | $0.433 | $21.47 |

All four configs share rank band 1. Paired comparisons with `fxh-claude`: mean difference 0.028 against `cc-claude`, 0.000 against `opencode-claude`, 0.083 against `pi-claude`; Holm-adjusted p = 1.0 for all three.

- **Overclaim 1.000.** In all 7 `moderate` trials where a fault was applied and the task failed, `fxh-claude` reported `success`. All 36 `moderate` trials report `success`.
- **Cost.** `fxh-claude` used 114,851,028 tokens over 72 trials, against 33.6 to 49.9 million for the other three. Its cost is 1.48 times `cc-claude`'s. On Track S in M5, `fx-claude` cost 1.34 times `cc-claude` (`reports/2026-10-20-m5-pilot.md`).
- **Calls fx did not run.** 189 `shell` calls in 66 of 72 trials ended with fx's "so fx did not run the call" error: 146 with truncated arguments, 43 with invalid JSON. The model retried them. They reached no injector, so no fault was drawn on them.

## 2. Checks

| Criterion | Result |
|---|---|
| Injection fidelity at least 99% | 114 of 114 verifiable faults delivered (100%), 156 applied: `err` 44, `poison` 40, `deny` 27, `trunc` 18, `falsefail` 14, `empty` 13. `trunc` is not verifiable from the trajectory |
| Infra failures under 5% | 0 of 72. One trial (`n-split-reports`, `moderate`, attempt 2) lost its result when the container restarted; it was moved to `jobs/pilot-fxh/_interrupted` and rerun with the same plan (reward 1) |
| Exposure floor | 2 `clean` trials below the floor of 4 eligible calls; 0 under `moderate` |

## 3. Analysis changes

Two changes in `cmca_analysis` were needed for the fault log to line up with fx trajectories. Neither changes the M5 boards (`tests/snapshots/release.json`).

1. Calls fx did not run (section 1) appear in the trajectory but never reach the injector. The order join now skips them (PR #60).
2. `injector-fxh` logs a `shell` call only for `action: run`; `interact` and `stop` act on a command already started. The join now skips those too. Before this change, 3 of 109 faults looked undelivered because the join had shifted.

Delivery checks for `empty` and `poison` read inside fx's `shell` JSON and `read_file` framing, as the V-27 conformance checker does (PR #60).

## 4. Cost

Recorded trial cost: $43.83 ($4.86 gate plus $38.97 pilot, including the rerun). The interrupted trial and four trials stopped during setup when a duplicate job started have no recorded cost. Vercel AI Gateway `total_used` was $67.63 after the run. No Anthropic API spend.
