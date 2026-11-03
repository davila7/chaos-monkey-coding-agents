---
title: What each new agent costs
date: 2026-11-03
summary: Where the benchmark stands after the first results, why every agent we add brings its own provider account, and how many dollars one more agent takes at today's size and at the size we are building toward.
---

The [previous post](/blog/tasks-a-strong-agent-cannot-skim) ended with three tasks and a plan for the first run with faults. Since then the benchmark grew to 12 tasks per track, ran its first results, and added two more agents. This post covers where it stands and the problem in front of it now: every new agent costs money in a new place.

Every number here comes from a committed report, `summary.json` or `DECISIONS.md` entry, linked where it is used. Costs are harness-reported, as in the [M5 report](https://github.com/davila7/chaos-monkey-coding-agents/blob/main/reports/2026-10-20-m5-pilot.md), not provider invoices.

## Where it stands

Six agents have run the benchmark tasks: Claude Code, OpenCode, Pi, Codex, fx and Muse Code. The first five use Claude Sonnet 5.5 and are on the [results site](https://chaos-monkey-coding-agents.vercel.app). Each published row is 144 trials: 12 tasks per track, the `clean` and `moderate` profiles, three attempts each.

Track S, tasks completed under faults:

| Agent | Completed | Sent |
| --- | --- | --- |
| Codex | 25 | 36 |
| fx | 25 | 36 |
| OpenCode | 25 | 36 |
| Pi | 24 | 36 |
| Claude Code | 21 | 36 |

Track N, tasks completed under faults:

| Agent | Completed | Sent |
| --- | --- | --- |
| Codex | 29 | 35 |
| Claude Code | 28 | 34 |
| OpenCode | 29 | 36 |
| Pi | 26 | 36 |

Codex, fx and OpenCode lead Track S with 25 of 36. Codex leads Track N with 29 of 35, followed by Claude Code and OpenCode. fx runs Track N through our fork with tool hooks, [fxh](https://github.com/davila7/chaos-monkey-coding-agents/blob/main/reports/2026-10-21-fxh-n-pilot.md), measured in a separate pilot. Muse Code runs Meta's own model, Muse Spark 1.3; its cost gate is done and its main run is not.

## One provider account per agent

The first three agents (Claude Code, OpenCode, Pi) all talk to the Anthropic API with one key. Every agent added since needed something else:

- **fx** reaches Claude through the Vercel AI Gateway, so its spend is billed by Vercel. Vercel's terms also restrict publishing benchmark results run through the Gateway ([V-17](https://github.com/davila7/chaos-monkey-coding-agents/blob/main/docs/verification/V-17.md)), which Anthropic's do not.
- **Codex** only speaks the OpenAI Responses API, which Anthropic does not serve. It runs on Claude through a bridge we wrote that translates Responses to Messages ([D-0044](https://github.com/davila7/chaos-monkey-coding-agents/blob/main/DECISIONS.md)). The spend is Anthropic's, but the bridge is one more component to verify per agent.
- **Muse Code** cannot run with Claude at all: Meta's terms forbid changing the harness to work with non-Meta models ([V-30](https://github.com/davila7/chaos-monkey-coding-agents/blob/main/docs/verification/V-30.md)). It runs Muse Spark, billed by Meta, on a separate account with its own key and its own balance. Its main run stopped when Meta's API started rejecting calls with a billing error, and it waits until that account has funds again.

So the rule we are living with: an agent comes with its model provider, and each provider is a new account, a new prepaid balance and new terms to read. On top of that, Anthropic spend has a hard ceiling of 200 USD per credit. The first credit covered everything up to M5. Codex used $40.04 of the second.

## What one more agent costs today

At the size of the published rows (144 trials per agent), the main run cost:

| Agent | Billed by | Track S | Track N | Total |
| --- | --- | --- | --- | --- |
| Pi | Anthropic | $8.91 | $21.47 | $30.38 |
| OpenCode | Anthropic | $9.50 | $20.67 | $30.17 |
| Codex | Anthropic | $11.12 | $22.81 | $35.47 |
| Claude Code | Anthropic | $11.76 | $26.28 | $38.04 |
| fx and fxh | Vercel | $15.73 | $38.97 | $54.70 |
| Muse Spark (projected) | Meta | | | $91.81 |

Sources: the [M5 report](https://github.com/davila7/chaos-monkey-coding-agents/blob/main/reports/2026-10-20-m5-pilot.md) for Claude Code, OpenCode, Pi and fx; the [Codex report](https://github.com/davila7/chaos-monkey-coding-agents/blob/main/reports/2026-10-31-codex-claude.md), whose total includes $1.54 for 14 trials cut by container restarts and rerun; the [fxh pilot](https://github.com/davila7/chaos-monkey-coding-agents/blob/main/reports/2026-10-21-fxh-n-pilot.md) for Track N of fx; and the Muse cost gate in [PR #80](https://github.com/davila7/chaos-monkey-coding-agents/pull/80), which projects the main run from 15 gate trials.

The main run is not the whole bill. Before it, each agent goes through verification and conformance against the pinned binary and a cost gate:

| Agent | Conformance | Gate | Main run | Total |
| --- | --- | --- | --- | --- |
| Codex | $0.69 | $3.88 | $35.47 | $40.04 |
| Muse Spark | $4.01 | $8.08 | $100.99 | $113.08 |

Muse's main run and total are projections. They include the 10% rerun allowance the plan reserves, and they are a lower bound, because Muse's reminder agents make calls that its logs do not price in full.

In short: one more agent on Claude costs about $35 to $45. One more agent on its own provider's model costs whatever that model costs; for Muse Spark, about $113.

## What one more agent costs at full size

The published rows are too small to separate the agents. The M5 report puts the minimum detectable difference at about 25 points, and the largest gap it observed between two agents on the same track was 11. The next milestone, M6, raises the tasks to 40 per track. That multiplies every trial count per agent:

- 40 tasks, n = 3: 480 trials per agent, 3.3 times today.
- 40 tasks, n = 5 (the SPEC design): 800 trials per agent, 5.6 times today.

Scaling each agent's main run by those factors, with the 10% rerun allowance, and assuming new tasks cost what the current ones cost (the same assumption D-0042 used to size M6):

| Agent | 40 tasks, n = 3 | 40 tasks, n = 5 |
| --- | --- | --- |
| Pi | $111 | $186 |
| OpenCode | $111 | $184 |
| Codex | $130 | $217 |
| Claude Code | $139 | $232 |
| fx and fxh | $201 | $334 |
| Muse Spark | $337 | $561 |

At the SPEC design, one Claude-backed agent takes most of a 200 USD credit, and Claude Code or Codex alone take more than one. Running the M5 agents (Claude Code, OpenCode, Pi and fx) at that size is the $916 that D-0042 estimated. Every new agent adds its row of this table, on its own provider's account.

## What we are doing about it

- **No new model runs without a cost estimate approved first.** That rule was already in the project; it now applies per provider, since each one has its own balance.
- **Task writing goes on without spend.** Tasks are validated with an oracle solution and a no-op agent, neither of which calls a model. Each track has 12 published tasks; the next batch of tasks is in review, on the way to 40.
- **Muse Spark resumes when its Meta account has funds.** Its 144-trial main run is projected at $100.99, and the gate numbers are in PR #80.

## Next

The question for M6 is no longer only which agents to add, but which providers to fund, and how much on each. With today's numbers, every agent at the SPEC design costs between $184 and $561. That is the figure to plan the next credits around.
