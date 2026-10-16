# Task review checklist

Derived from the Agentic Benchmark Checklist (ABC) in Zhu et al., "Establishing Best Practices for Building Rigorous Agentic Benchmarks", arXiv:2507.02825 (v5). Item ids and wording follow the paper's Figures 2 to 4. SPEC 13.1 requires every item to be marked addressed, not applicable, or a known limitation.

The first part marks each item for the benchmark as a whole. The second part is the review a task pull request carries (SPEC 10.4 item 6); the owner's merge of that pull request is the sign-off.

## Benchmark-level marking

### Task validity

| Item | ABC check | Marking | How |
|---|---|---|---|
| T.1 | Versions of all tools are clearly specified | Addressed | Base images pinned by digest; harness versions and model ids pinned in `configs/`; service images versioned |
| T.2 | Required API tools are consistently accessible | Addressed | Mock services run inside the task environment; the only external API is the model endpoint |
| T.3 | Evaluation terminates or handles errors if an API becomes inaccessible | Addressed | Harbor timeouts; trials with infrastructure exceptions are flagged by the analysis (`infra_failures`) and excluded from scores |
| T.4 | Residual data or state fully cleared between runs | Addressed | Every trial runs in fresh containers; services start from a seeded state |
| T.5 | Agent completely isolated from ground truth | Addressed, checked per task | Tests and solutions are not in the image; admin endpoints unreachable from the agent (V-13) |
| T.6 | Setup does not change over time | Addressed | No live websites; generated environments use fixed seeds |
| T.7 | Annotated ground truth verified for correctness | Addressed, checked per task | Oracle passes; human review of the tests |
| T.8 | Each task verified to be solvable | Addressed | Oracle under `clean`, and on Track S under every fault profile, in CI |
| T.9 | Oracle solver that solves all challenges | Addressed | `solution/solve.sh` for every task, run by the `task-validation` workflow |
| T.10 | Free of vulnerabilities exploitable to pass without completing the task | Known limitation | `nop` scores 0 and each task's walkthrough lists shortcut attempts that score 0; the reward-hacking pass with frontier agents (D-0012 item 4) has not run yet |

### Outcome validity

| Item | ABC check | Marking | How |
|---|---|---|---|
| O.a.1 | String matching considers semantically equivalent expressions | Checked per task | Applies to tasks with answer files; the instruction fixes the format and the verifier normalizes it |
| O.a.2 | Handles redundant words | Checked per task | As O.a.1 |
| O.b.1 | Substring matching handles negation modifiers | Not applicable | No verifier uses substring matching on free text |
| O.b.2 | Robust against listing all possible answers | Checked per task | Answer files are structured; extra entries fail the check |
| O.b.3 | Ground truth complex enough to prevent guessing | Checked per task | |
| O.c.1 | LLM judge accuracy evidence | Not applicable | No LLM judges (SPEC 10.3) |
| O.c.2 | LLM judge resists adversarial inputs | Not applicable | No LLM judges |
| O.d.1 | Test cases verified for correctness and quality | Addressed, checked per task | Human review |
| O.d.2 | Test quality measured with objective metrics | Known limitation | Coverage and complexity of verifier tests are not measured |
| O.e.1 | Fuzz inputs address edge cases | Checked per task | Applies where the verifier runs agent code on held-out inputs |
| O.e.2 | Comprehensive coverage of input variations | Checked per task | As O.e.1 |
| O.e.3 | Inputs the code under test is sensitive to | Checked per task | As O.e.1 |
| O.f.1 | End-to-end tests exercise all relevant parts | Checked per task | |
| O.f.2 | No flaky results | Addressed, checked per task | Deterministic services and seeds; the oracle reruns in CI on every change |
| O.g.1 | Ground truth includes all states achievable after success | Checked per task | |
| O.g.2 | Checks relevant and irrelevant states | Checked per task | Track S verifiers check that untouched records stay unchanged |
| O.g.3 | State complex enough to prevent trivial modifications | Checked per task | |
| O.h.1 | Required answer formats specified | Checked per task | |
| O.h.2 | Minimizes success by random guessing | Checked per task | |
| O.i.1 | Quality metrics prevent exploitation | Addressed | `STATUS.json` never affects the reward; overclaim is reported separately (SPEC 11, M7) |

### Benchmark reporting

| Item | ABC check | Marking | How |
|---|---|---|---|
| R.1 | Fully or partially open-sourced | Addressed | Code under Apache-2.0, task data under CC BY 4.0 (SPEC 16) |
| R.2 | Open-source evaluation harness | Addressed | Harbor plus the `cmca` CLI and `cmca_harbor` agents |
| R.3 | Measures against data contamination at release | Known limitation | Canary string in every file the agent never sees; the private holdout (SPEC 10.5) starts with v1.0, so pilot tasks are all public |
| R.4 | Plans to keep challenges updated | Addressed | Per-task versions (D-0012), holdout rotation in minor releases (SPEC 10.5) |
| R.5 | States the relation between capabilities and measures | Known limitation | Described in SPEC 1 and 11; `METHODOLOGY.md` is not written yet |
| R.6 | States the evaluation subject | Addressed | A config is a harness plus a model; boards separate fixed-model and native comparisons (SPEC 5) |
| R.7 | Describes steps to prevent, identify and correct flaws | Addressed | This checklist, the validation pipeline, the task-bug form and triage (`CONTRIBUTING.md`) |
| R.8 | Qualitative discussion of unavoidable flaws | Known limitation | SPEC 13.2 lists threats to validity; `METHODOLOGY.md` is not written yet |
| R.9 | Quantitative analysis of unavoidable flaws | Known limitation | Delivery reconciliation and validity counts (M12) per row; no analysis of verifier noise yet |
| R.10 | Statistical significance | Addressed | Hierarchical bootstrap intervals, paired permutation tests with Holm correction, rank bands (SPEC 12) |
| R.11 | Guidance on interpreting results with flaws | Known limitation | Planned for `METHODOLOGY.md` |
| R.12 | Non-AI baselines | Known limitation | No human baseline is planned |
| R.13 | Trivial agents | Addressed | `nop` per release |

## Per-task review

Copy this block into the task pull request, one per task, and fill each line with yes, no, or n/a and a short reason where the answer is not obvious.

```markdown
### <task id> <version>

- [ ] T.5 Nothing in `instruction.md` or `environment/` reveals the answer or the tests; services hold ground truth behind the admin endpoint.
- [ ] T.7 The tests check what the instruction asks for, no more and no less.
- [ ] T.8 / T.9 Oracle 1 under clean (and every profile on Track S), nop 0, in the task-validation run.
- [ ] T.10 Shortcut attempts listed in `solution/WALKTHROUGH.md` score 0.
- [ ] O.a / O.b / O.h Answer formats are stated in the instruction; equivalent answers are accepted; listing every candidate fails.
- [ ] O.d.1 Every test was read; each one can fail.
- [ ] O.e Held-out inputs exercise the edge cases the instruction or docs state.
- [ ] O.f.2 No time, randomness or network dependence in the verifier.
- [ ] O.g Irrelevant state is checked unchanged; a trivial or partial change fails.
- [ ] Banned words and the canary pass lint; the task version follows the bump rule.
```
