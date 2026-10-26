<p align="center">
  <img src="assets/banner.png" alt="Chaos Monkey for Coding Agents" width="100%">
</p>

# Chaos Monkey for Coding Agents

How coding-agent harnesses recover when their tools fail. A fault-injection benchmark.

CMCA injects seeded faults into tool calls at two layers: an MCP proxy in front of mock services (Track S) and each harness's own built-in tools (Track N). It measures task success under faults, recovery behavior, the cost of recovery, and whether the agent reports its outcome honestly. The full design is in [SPEC.md](SPEC.md).

Results and build log: [chaos-monkey-coding-agents.vercel.app](https://chaos-monkey-coding-agents.vercel.app) (source in `packages/site`).

## Results

First results (M5, 504 trials, 2026-10-20): [report](reports/2026-10-20-m5-pilot.md), boards in [results/2026-10-20-m5](results/2026-10-20-m5), live on the [site](https://chaos-monkey-coding-agents.vercel.app). All configs use `claude-sonnet-5-5` with reasoning effort `medium`.

Track S, tasks completed under the `moderate` fault profile (12 tasks x 3 attempts = 36 sent):

| Harness | Completed | Faulted Success |
|---|---|---|
| fx 0.0.13 | 25 / 36 | 69.4% |
| OpenCode 1.18.35 | 25 / 36 | 69.4% |
| Pi 1.0.3 | 24 / 36 | 66.7% |
| Claude Code 2.1.289 | 21 / 36 | 58.3% |

fx and OpenCode lead Track S. On Track N (built-in tools) Claude Code leads with 0.833 Faulted Success, then OpenCode 0.806 and Pi 0.722. Intervals, retention, overclaim, poison propagation and cost per success are in the report.

## Status

- **M5 (first results): done.** Track S: 4 harnesses (Claude Code, fx, Pi, OpenCode). Track N: 3 harnesses (Claude Code, Pi, OpenCode); fx 0.0.13 cannot intercept its built-in tools ([V-22](docs/verification/V-22.md)). Track N injection fidelity was 95.1%, below the 99% bar (report section 3).
- **fxh, a fork of fx with tool hooks** ([davila7/fxh](https://github.com/davila7/fxh), D-0040). It passes conformance on all 6 fault types ([V-27](docs/verification/V-27.md), `capabilities/fxh@0.0.13-h1.json`). Track N pilot, 72 trials: Faulted Success 0.806, 114 of 114 verifiable faults delivered, overclaim 1.000, cost 1.48 times Claude Code ([report](reports/2026-10-21-fxh-n-pilot.md)). It joins the boards in M6.
- **Failed shell commands (D-0042).** The Track N fidelity misses had one cause: the Claude Code and Pi injectors returned failed shell commands unchanged. Both injectors are fixed, and the `probe-shell-fail` conformance probe is ready; its runs with the model are pending.
- **M6 task suite (D-0043): in progress.** Target 40 tasks per track plus a private holdout, validated with `oracle` and `nop` (no model calls). On `main`: 12 Track N and 12 Track S tasks. Batch 1 (14 more, 7 per track) is in review. The M6 budget is not decided yet.

Decisions are in [DECISIONS.md](DECISIONS.md); verification evidence for third-party behavior is in [docs/verification](docs/verification).

## Development

Requirements: Node 24 (22.12 or later works locally), pnpm 10, uv.

```bash
pnpm install
pnpm build
pnpm test
pnpm lint
pnpm bench:decide
uv sync --all-packages
uv run pytest
```

Layout:

| Path | Contents |
|---|---|
| `packages/fault-engine` | Fault schedule, trial state store, catalog, schemas, `tt-decide` CLI |
| `packages/injector-claude-code`, `injector-pi`, `injector-opencode`, `injector-fxh` | Native injectors for Track N |
| `packages/mcp-fault-proxy`, `packages/mock-services` | Track S fault proxy and mock services |
| `packages/cli` | `cmca` CLI (`lint`, `task-bump`, `analyze`) |
| `packages/site` | Results site (Next.js static export for Vercel) |
| `python/cmca_harbor` | Harbor custom agents, conformance runner, trial planner |
| `python/cmca_analysis` | Analysis pipeline: delivery reconciliation, metrics, bootstrap intervals, boards |
| `profiles/` | Fault profiles |
| `configs/` | Harness configurations |
| `datasets/` | Task datasets, conformance probes and the canary |
| `capabilities/` | Capability files generated from conformance |
| `results/` | Conformance, task validation, calibration, smoke, pilot and release evidence |
| `reports/` | Run reports |
| `docs/verification/` | Evidence for third-party behavior |

## Affiliations

To be completed by the maintainers before the first public release (SPEC 13.2).

## License

Code: Apache-2.0 ([LICENSE](LICENSE)). Task data: CC BY 4.0 ([LICENSE-DATA](LICENSE-DATA)); task files carry a canary string and must not be used for model training.
