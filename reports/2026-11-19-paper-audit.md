# Paper revision after the academic audit (2026-11-19)

Scope: `paper/` at main `e0a05895`, release `results/2026-11-18-m6`, against the external academic audit of the 2026-11-19 draft (29 findings) and an internal audit the same day. Decision: D-0056. No model calls. Every new number in the paper comes from `python -m cmca_analysis paper` over the release; snapshot tests in `python/cmca_analysis/tests/test_paper.py` cover the new tables.

Status values: fixed, partly fixed, pending (needs work beyond a first version), not a defect (the finding did not hold).

## P0

| ID | Verdict on the finding | Status | Change and evidence |
|---|---|---|---|
| P0-01 Causal wording | Real. METHODOLOGY 2.2 lists Pi effort `high`, summarized thinking, OpenCode title model, Gateway route, Codex bridge. | fixed | Abstract, 4.2 "What the fixed-model condition controls" and Section 8 now speak of configuration-level comparison and list each difference. |
| P0-02 "Unmodified" | Real. fxh is a fork; Codex uses our bridge. | fixed | Abstract, 4.1, 6.2, related work "Position", threats and disclosures name fxh as the author's fork and the bridge as ours; the fxh row is stated not to measure stock fx. |
| P0-03 Unequal exposure | Real. Under `moderate`, applied faults per trial on Track N range 1.83 (Pi) to 3.78 (fxh); Track S 4.89 to 5.01 (`<board>/<config>/summary.json`, `profiles.moderate.validity`). | partly fixed | New Table 6 (exposure: applied, per trial, verifiable, delivered, not verifiable) and a paragraph in 7.1. No exposure-normalized analysis (recommendation below). |
| P0-04 Curves are not base rate only | Real. `profiles/*.yaml` change cap, persistence and targeted rates with the base rate. | fixed | New profile table (Table 3); curve axis labeled by profile; caption, AUC definition and 7.4 call them severity levels. |
| P0-05 Recovery metrics missing | Real. Defined in Section 5 but not reported; the release summaries already hold them. | partly fixed | New Table 8: fault-event outcome shares, duplicate side effects (0 of 52 to 54 per Track S config), median moderate/clean token and step ratios; Table 7 adds pass^3. Trajectory case studies not added. |
| P0-06 Order independence | Real. Cap, occurrence and persistence make the applied decision state dependent (D-0003). | fixed | 3.2 separates candidate draw from applied decision; Figure 1 caption corrected. |
| P0-07 Deviations and calibration | Real. Calibration uses `cc-claude` clean (METHODOLOGY 2.5). | partly fixed | 4.3 states the calibration rule and its bias; Table 11 lists every deviation from `reports/2026-11-18-m6-release.md` section 5. No sensitivity analysis. |
| P0-08 Fidelity covers verifiable faults only | Real. `trunc`, `drift`, `rate` are not verifiable (METHODOLOGY 4). | fixed | 5.2 defines verifiable faults; Table 6 shows not-verifiable counts; 70% (Track S) and 75% (Track N) of applied faults are verifiable. |

## P1

| ID | Verdict | Status | Change and evidence |
|---|---|---|---|
| P1-01 Same reasoning effort | Real. | fixed | Wording is "same nominal reasoning setting" with the Pi difference stated. |
| P1-02 Overclaim denominators | Real gap in the paper; no calculation error. The denominator is trials with at least one applied fault and reward 0 (`trials.py`), e.g. fx Track S 27, not 28; missing status counts as no report. | fixed | Table 7 gives k/n, no-report count and bootstrap intervals; 5.1 defines "faulted trial" and the denominator. |
| P1-03 87/107 vs 0.815 | Not a defect. Faulted Success is the mean over tasks of c_t/n_t (`metrics.pass1`). | fixed | Formula uses n_t; Table 5 caption explains. |
| P1-04 Power and bands | Real gap. | fixed | 5.3 states the 10-pair family, exploratory tests, band meaning; 7.1 gives the unadjusted p of the largest pair (0.061) and tasks needed for 10 points (92 to 144 Track S, 42 to 74 Track N). |
| P1-05 Cost definition | Real. | fixed | 5.1 and 7.5 state the denominator (successes under `moderate`) and each harness's cost source; rows are called approximate. No single-price re-costing. |
| P1-06 Task description | Real. | partly fixed | 4.3 describes the task families and that all are synthetic. No per-category table. |
| P1-07 Poison is a token proxy | Real. | fixed | Called a token-based proxy and a lower bound; Table 7 gives k/n and intervals. No manual review. |
| P1-08 Native axis not run | Real. | fixed | 4.2 says it was not run. |
| P1-09 Reproducibility | Real. The paper had no URL, model or versions. | fixed | Table 2 (configs from the release), "Code and data availability" with repository, release, tags `m6-2026-11-18` and `pre-m6-2026-11-10` (both verified on origin), seed, HF dataset; appendix gives the command. |
| P1-10 Vercel terms | Resolved by the owner: Vercel gave the OK to publish (2026-11-19). | fixed | Provider-terms paragraph and its internal source comment removed; the Gateway is named only as the model route of fx and fxh. |
| P1-11 Novelty and bibliography | Partly real. "To the best of our knowledge" added. The audit's claim that ref [18] has the wrong title does not hold: arXiv 2605.27922v2 is titled "Harness-Bench: Evaluating Agent Harnesses across Models and Realistic Workflows" (V-19; the audit quotes v1). arXiv 2610.32483 exists and is now cited, with 2608.26218 and 2609.32459 found in the same search. ResiliBench was not found on arXiv and is not cited. The ", ." punctuation is fixed. All 19 arXiv entries were checked against export.arxiv.org. | fixed | `refs.bib`, 2. |
| P1-12 Uncertainty in figures | Partly real. | partly fixed | Intervals added for overclaim and poison; curve figure stays point estimates with the caption saying so. |

## P2

| ID | Status | Change |
|---|---|---|
| P2-01 Units label | fixed | Columns "Scheduled units" and "No counted trial". |
| P2-02 Research questions | fixed | RQ1 to RQ3 in the introduction, mapped to metrics and result subsections. |
| P2-03 Conclusion | fixed | Section 9. |
| P2-04 Figure 1 labels | partly fixed | Caption corrected; the figure itself is unchanged. |
| P2-05 Version table | fixed | Table 2. |
| P2-06 Infrastructure failures | pending | Counts are in the release and stage reports, not in the paper. |
| P2-07 Faulted trial definition | fixed | 5.1. |
| P2-08 License, COI, affiliation | partly fixed | Disclosure added. License and affiliation are owner decisions (CC BY 4.0 planned in D-0050). |
| P2-09 AI assistance statement | fixed | Kept and expanded. |

## Internal audit (same day)

- Model and versions missing: fixed (Table 2).
- No repository or dataset links although the GitHub repository is now public: fixed.
- "Faulted tasks" for trial counts: fixed ("faulted trials").
- Robustness AUC undefined: fixed (5.1).
- Injector discovery not reported: partly fixed. 23 trial runs carry the flag, some under `clean`; the paper calls the flag coarse. Count not in the paper.
- Codex Track N fidelity 0.977 under the 99% stop rule: explained in 7.5 (totals include replaced originals).
- PDF metadata, draft date, pass^1 header, legend contrast: fixed.

## Pending for later versions (no new runs required unless stated)

1. Exposure-normalized or exposure-stratified Track N analysis (existing data).
2. Sensitivity of rankings to the deviations: stage, injector version, rerun rule (existing data).
3. Two trajectory case studies, one recovery and one failure after a fault (existing data, manual selection).
4. Human validation of the fault-event outcome rules on a sample (existing data, human time).
5. Per-category task table and infrastructure failure counts in the paper (existing data).
6. Owner: affiliation and license choice at submission.

## Recommended experiments (not results)

- More tasks per track (about 100 or more for 10-point differences at n = 3, per the power figures above).
- Calibration with a configuration outside the comparison, or with all configurations.
- A base-rate-only ablation that holds cap, persistence and targeted faults fixed.
- Exposure-matched native-track runs.
- Delivery instrumentation for `trunc`, `drift` and `rate`.
- Runs with other main models and the native axis.
