# codex-claude results report

Codex CLI 0.163.0 with `claude-sonnet-5-5` (reasoning `medium`) through `packages/responses-bridge`, on the M5 tasks, profiles, `n` and seed (D-0044 item 6, D-0045). Release `results/2026-10-31-m5-codex`, built from the M5 evidence and `results/pilot/2026-10-30-codex-{n,s}/` with the D-0045 join. The site data is `packages/site/data/results.json` from the same run.

## 1. What ran

144 trials: 12 tasks per track, `clean` and `moderate`, n = 3, seed `m5-2026-10-19`. No infrastructure failure, so no reruns. Commands: `results/pilot/2026-10-30-codex-{n,s}/commands.txt`. Release command:

    uv run python -m cmca_analysis analyze --release 2026-10-31-m5-codex --seed m5-2026-10-19 --evidence ../results/pilot/2026-10-19-m5-s --evidence ../results/pilot/2026-10-19-m5-n --evidence ../results/pilot/2026-10-30-codex-s --evidence ../results/pilot/2026-10-30-codex-n --out ../results/2026-10-31-m5-codex --site ../packages/site/data/results.json

(from `python/`). Every number for the M5 configs in this release equals `results/2026-10-20-m5`; the only differences are the codex rows, the comparisons that include `codex-claude`, and Holm-adjusted p values on Track N, which now correct over six comparisons instead of three.

## 2. Results

From `results/2026-10-31-m5-codex/site-data.json`.

| Board | Faulted tasks completed | `clean` pass^1 | RR | Overclaim rate | $ per success |
|---|---|---|---|---|---|
| Track S | 25 of 36 | 1.0 | 0.6944 [0.4722, 0.8889] | 0.9091 | 0.237 |
| Track N fixed model | 29 of 35 | 1.0 | 0.8333 [0.6667, 0.9722] | 0.8333 | 0.4198 |

Track S: `codex-claude` 25 of 36, the same as `fx-claude` and `opencode-claude`; `pi-claude` 24, `cc-claude` 21. Track N: `codex-claude` and `opencode-claude` 29, `cc-claude` 28 of 34, `pi-claude` 26. Every config is in band 1 on both boards. One Track N `moderate` trial is excluded (35 sent), so `pass3_moderate` is not reported for codex on Track N.

## 3. SPEC 19 checks

| Criterion | Result | Status |
|---|---|---|
| Injection fidelity at least 99% | Track S 121 of 121 verifiable faults delivered (100%). Track N 87 of 88 (98.9%) (`results/pilot/2026-10-30-codex-{s,n}/summary.json`, `moderate`) | Not met on Track N |
| Infra failures under 5% | 0 of 144 | Met |

The Track N miss is an `empty` fault on a command still running when `exec_command` returned (`n-bisect-regression`, `moderate` attempt 2). Codex fires `PostToolUse` only when such a process ends, on a later `write_stdin` poll, and never if it does not end (V-02 addendum, 2026-10-31). The model saw the real partial output. An injector fix needs its own plan.

## 4. Cost

Model spend from the bridge usage logs at Anthropic list prices: main run $35.4747, including $1.5447 for 14 trials cut by container restarts and rerun with `harbor jobs resume`. D-0044 in total $40.0439 (conformance $0.6902, gate $3.8790, main run). No model calls for this report.

## 5. Config notes for the board

- The model route is the bridge: Codex speaks only the Responses API, and the bridge translates to the Messages API.
- Hosted web search and sub-agents are disabled; MCP tools are offered up front, not through Codex's tool search (D-0044 notes 3 and Progress 2).
- Codex has no read, search or list tool, so `fs.read`, `fs.search` and `fs.list` faults never apply.
