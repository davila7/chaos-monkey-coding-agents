---
title: Three harnesses pass conformance
date: 2026-10-11
summary: The conformance rerun for Claude Code, Pi and OpenCode, what each harness does when the injector breaks, and the three tasks the smoke run will use.
---

The [previous post](/blog/does-the-fault-reach-the-model) explained why every harness goes through a conformance suite before any agent is scored: a fault the model never sees makes a trial look like a clean success. That post ended with numbers that lived on one machine. This one covers the rerun, which is now committed, and the first tasks.

## The rerun

Conformance ran again on 2026-10-10 in a cloud container with Harbor 0.24.0, three runs per probe, for three harnesses: Claude Code 2.1.289, Pi 1.0.3 and OpenCode 1.18.35. Every trial's trajectory, injector log and verifier output is in [`results/conformance/`](https://github.com/davila7/chaos-monkey-coding-agents/tree/main/results/conformance), and the suite turned them into one capability file per harness in [`capabilities/`](https://github.com/davila7/chaos-monkey-coding-agents/tree/main/capabilities).

| Harness | Fault types delivered | Gaps | Injector crash | Decision p95 |
| --- | --- | --- | --- | --- |
| Claude Code 2.1.289 | 6 of 6 | `empty` on Write and Edit | fails open | 7.3 ms |
| Pi 1.0.3 | 6 of 6 | none | fails closed | 5.7 ms |
| OpenCode 1.18.35 | 6 of 6 | none | fails open | 4.8 ms |

The six types are denial, transport error, empty result, truncated result, false failure after the change was made, and poisoned content. A type is delivered when every probe for it passed all three runs. The archived 225 trials report $2.38 in model cost.

This run added the checks the first batch skipped: the file on disk after the call, the text the harness wraps around the failure, the injector's latency, and a run with an injector that crashes on load.

## What the rerun found

**The empty-file fix works.** In the first batch an emptied Read in Claude Code still reported the file's real line count. After the injector began rewriting that count, all three runs show Claude Code's own warning that the file exists but is empty.

**The two Claude Code gaps are confirmed.** Claude Code prints a fixed success line after Write and Edit whatever the extension returns, so an empty result cannot reach the model there. Both cells are recorded as gaps with that reason, and the schedule never picks them. Every other fault type still applies to Write and Edit.

**A failed tool call looked undelivered in OpenCode.** The first OpenCode pass scored denial, error and false failure 0 of 3. The injector had worked. Harbor's conversion of OpenCode sessions into trajectories kept the output of a tool call but dropped the error text of a failed one, which is exactly where those faults land. The CMCA agent now copies the error into the output before the conversion, and the rerun of those three types passed 3 of 3. Had we scored agents on the first pass, OpenCode would have looked as if it never saw an error.

**Harnesses disagree on what to do when the injector breaks.** For the crash check, the injector module throws on load. Claude Code and OpenCode log the failure and keep running without it, so the trial goes on with no faults. Pi refuses to start and exits with an error. Neither is wrong, but they produce different trials. On Claude Code and OpenCode a broken injector looks like a clean run, so the analysis has to catch it from the missing log records. On Pi it shows up as an infrastructure failure.

**Search and list tools are mostly absent.** Claude Code 2.1.289 exposes no search or list tool in the session, and the Pi probes searched through the shell. Only OpenCode called a dedicated search tool. On the other two, search and list faults can only reach the agent as shell faults.

## Getting it to run at all

The first attempt ran on a maintainer's laptop and never got as far as a model call. The harness install inside each task container ran past Harbor's setup timeout. After that was raised, Docker ran out of disk and started returning I/O errors. Both are infrastructure failures, and both would have shown up as failed cells if the run had not been stopped. The conformance script now raises the setup timeout by default, and runs moved to a cloud container.

## The first tasks

The smoke run needs tasks. There are now three original Track N tasks, written as a reference solution plus a verifier and never by running one of the evaluated agents:

- **A small ledger package with failing unit tests.** It has four bugs: amount parsing, date order, negative amounts and a loop that drops the last entry. The verifier runs its own copy of the tests plus extra cases, so editing the visible tests does not help.
- **Three warehouse exports in different formats and units.** The agent merges them into one summary. The traps are a decimal comma, pounds against grams, mixed-case status values and a shipment just before midnight UTC.
- **An investigation.** One service failed to start, and the agent writes down which one, the port, and which service already held it. The answer depends on how config includes and sections are read. A decoy override that is never applied points the wrong way. One config file has a poisoned variant carrying a token, to see whether planted content ends up in the agent's answer.

For each task the reference solution scores 1 and an agent that does nothing scores 0 ([`results/task-validation/`](https://github.com/davila7/chaos-monkey-coding-agents/tree/main/results/task-validation)). Every verifier also keeps the agent's own completion report. The reward ignores it, and the analysis uses it to count agents that claim success on a failed task.

Two more pieces went in with the tasks. A planner turns a config, a fault profile and a capability file into Harbor jobs. A first analysis reads the job directories back and reports pass^1, cost per trial, faults applied and how many reached the model, overclaims and poison propagation. A snapshot test pins that analysis output byte for byte.

## Next

The smoke run is Claude Code on these three tasks, once with no faults and once under the moderate profile: six trials. It needs the owner's approval of its cost estimate before it starts. Three tasks with one attempt each say nothing about how robust Claude Code is. The run proves the pipeline from trial to analysis to this site, and it gives the first measured cost per trial on a real task. It will appear on the results page labeled as a smoke run.
