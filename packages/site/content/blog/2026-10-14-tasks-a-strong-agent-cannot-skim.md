---
title: Tasks a strong agent cannot skim
date: 2026-10-14
summary: Four runs of Claude Code on the Track N tasks, why the first three told us nothing about robustness, and what it took to get a task that needs more than a handful of tool calls.
---

The [previous post](/blog/three-harnesses-pass-conformance) ended with three tasks and a smoke run waiting for approval. This post covers that smoke run and three clean pilots after it. None of them measures robustness yet: every run below uses the clean profile or applied no faults. They answer an earlier question, which is whether the tasks give faults anything to hit.

Every number here comes from a `summary.json` and the trajectories under [`results/`](https://github.com/davila7/chaos-monkey-coding-agents/tree/main/results). All runs used Claude Code 2.1.289 with `claude-sonnet-5-5` through Harbor 0.24.0.

## Two gates a task has to pass

SPEC 10.3 sets two gates for tasks in clean runs, before any fault is applied:

- **Exposure floor.** Each trial makes at least 8 eligible tool calls. A fault can only land on a tool call, so an agent that finishes in three calls gives the injector almost nothing to work with.
- **Difficulty band.** Clean pass^1 sits between 0.4 and 0.9. A task every agent always solves cannot show a robustness drop at the top end, and one nobody solves cannot show it at all.

## Smoke run: the pipeline works, the tasks are too small

The smoke run had six trials, one per task under the clean profile and one under the moderate profile. All six scored 1 and the total cost was $0.19. The pipeline from trial to analysis to the site worked end to end.

It also showed the problem. Trials made between 2 and 4 eligible calls, all through the shell, and the moderate profile applied no faults at all. The agent printed every relevant file in one `cat`, fixed everything in one Python heredoc and wrote its report. With a base rate of 0.15 and nine eligible calls across three moderate trials, zero faults is an unremarkable outcome.

## Pilot 1: sequential design is not enough

The first revision of the tasks layered the problems: one bug masked the next, and one file named the file to read next. The idea was that the agent would have to work step by step. Six clean trials passed 6 of 6 for $0.67, with 4 or 5 eligible calls each.

The trajectories show why the layering did not work. At a few hundred to a few thousand lines, a frontier model reads the whole environment in one loop and reasons past the layers. In the ledger task it fixed five layered bugs in one edit and never re-ran the tests.

## How much one tool output holds

Making the tasks bigger only helps if the material does not fit in one tool output, so we measured that limit first ([V-21](https://github.com/davila7/chaos-monkey-coding-agents/blob/main/docs/verification/V-21.md)). In the pinned Claude Code binary, a Bash call returns at most 30,000 characters inline. Past that, the model gets a 2,000 character preview and the path of a file holding the rest. The Read tool refuses anything above 25,000 tokens unless the agent asks for a range.

Measuring this corrected one of our own numbers. We had said outputs of about 33,000 characters came back whole. Harbor's trajectory appends the raw stdout to the text the model saw, so each output was counted twice. The largest output the model actually saw in pilot 1 was 16,824 characters.

## Pilot 2: big environments, still easy

The second revision rebuilt each environment from a deterministic generator that runs while the image is built:

- the ledger became a library of about 80 Python files with 755 visible tests;
- the shipments task got 131 export files totalling 6.1 million characters;
- the port investigation got 40 services, 39 config revisions and 325,649 log lines, plus a local status service that holds state no file contains.

Six clean trials passed 6 of 6 for $1.44. The ledger and port tasks now cleared the floor, with 14 to 16 and 10 to 11 calls. Shipments did not, with 7 and 5. Claude Code's large-output window showed up in the ledger and port trajectories, so the size was doing something.

The trajectories again showed one cause for all three tasks: the docs named every trap. Docs that said which depot used which format, or which revision changed a port, let the agent read them once and run a known plan. In one shipments trial the agent wrote its parser in a single call from the docs and never ran the checker the task provides.

## Pilot 3: rules in the docs, instances in the data

The third revision kept every rule in the docs but removed every statement of where a rule applies. The agent now has to find the instances with tools the task ships:

- **Ledger:** an audit tool that reports failed checks per rule and per package, without saying where. It has nine new bugs that no visible test exposes.
- **Shipments:** the generator's seed decides which depot uses which convention, and the held-out data used for scoring places them differently.
- **Port investigation:** the status service only answers port queries over a time window, a page at a time. A second host fails in the same window for a different reason.

Before the run, each task was checked against an attempt written only from the docs and the first lines of each file. All three such attempts score 0.

Fifteen clean trials, five per task, cost $6.53:

| Task | Passed | Eligible calls per trial |
| --- | --- | --- |
| Ledger | 5 of 5 | 23 to 29 |
| Port investigation | 5 of 5 | 10 to 12 |
| Shipments | 4 of 5 | 10 to 29 |

Every trial cleared the floor, with a minimum of 10 calls. Overall pass^1 is 14 of 15, or 0.93, with a Wilson 95% interval of 0.70 to 0.99. The point estimate sits above the 0.9 ceiling, but the interval includes it, so 15 trials cannot show the tasks are too easy. For comparison, pilot 2's 6 of 6 is what a task with a true pass rate of 0.9 produces 53% of the time.

The one failure is the kind the tasks were built for. On held-out data, the agent's decoder for UTF-16 files removed one character after Python had already dropped the byte order mark. In one depot that character was the opening brace of a metadata line. The line stopped parsing, so two exports were applied out of order and the depot ended up with one shipment too many. On the visible data the same bug was harmless, and the agent's script passed the task's own checker. We confirmed the cause by replaying the agent's commands in a fresh container and comparing its output with the reference solution ([`failure-replay.txt`](https://github.com/davila7/chaos-monkey-coding-agents/blob/main/results/pilot/2026-10-14-cc-claude-clean-d26/failure-replay.txt)).

## What is still open

**Exposure is almost all shell.** Of 261 eligible calls in pilot 3, 255 went through Bash, plus 4 Reads and 2 Writes. SPEC 7.3 treats this as part of what is measured: with this harness and model, file faults mostly reach the agent through the shell.

**The poisoned file has never been eligible.** The port task plants a stale copy of one config file. The stale copy is served only when the agent opens the file with the Read tool, and in every run so far the agent opened it with `cat`. Reaching shell reads would mean rewriting the output of shell commands, which needs its own SPEC-level decision.

**Three tasks are a pilot, not a track.** These runs settle the method: rules in the docs, instances in the data, and a docs-only attempt that must fail. They do not settle the difficulty band, which needs more tasks and more attempts.

## Next

The step we propose next is a run with faults: the same tasks under the moderate profile, compared against this clean baseline. Like every model run, it needs the owner's approval of a cost estimate first. It would be the first run that says anything about robustness.
