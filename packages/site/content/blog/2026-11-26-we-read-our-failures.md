---
title: We read 80 of our failures
date: 2026-11-26
summary: Anthropic's guide to agent evals says to read the transcripts before trusting a score. We had never done it, so we read 80 failed trials from M6. Most failures were the agents' own, but a third came from tasks that gave the agent no fair way to pass.
---

Anthropic published a guide called [Demystifying evals for AI agents](https://www.anthropic.com/research/demystifying-evals-for-ai-agents). Most of it describes things this benchmark already does: tasks with reference solutions, tests that check the final state, a fresh container for every attempt, several attempts per task. One piece of advice we had not followed. The guide says not to trust a score until you have read the transcripts of the failures, because a failure can come from the agent, from the task or from the test. A failure should look fair: it should be clear what the agent got wrong.

We had run 3,011 trials for [M6](/blog/m6-is-done) and had never read a failed one to ask that question. Two numbers in the release made it urgent. Two tasks were never passed under faults by any agent, although agents passed both most of the time without faults. And one of our headline findings is that agents usually report success when they have actually failed. That finding is only true if the failures are fair.

## How we did it

We picked 80 failed trials under the `moderate` fault profile and wrote the list down before reading any of them, so we could not choose the convenient ones. It held all 30 trials of the two tasks nobody passed, plus 50 picked at random from the failed trials where the agent reported success.

For each trial we read what the agent did, what the faults changed and which check failed, and gave it one of four labels:

- **Agent error**: the agent had what it needed and got it wrong.
- **Unfair fault**: a fault we injected left no reasonable way to pass.
- **Test rejects a valid answer**: the work was right and the check said no.
- **Unclear**: the evidence does not decide.

No model calls were needed. The trajectories were already in the repository, and the test logs that were missing from it were in our job archives.

## What we found

| Group | Trials | Agent error | Unfair fault | Test rejects valid answer | Unclear |
| --- | --- | --- | --- | --- | --- |
| The two tasks nobody passed | 30 | 7 | 20 | 0 | 3 |
| Random sample of failed trials that reported success | 50 | 35 | 13 | 0 | 2 |
| All | 80 | 42 | 33 | 0 | 5 |

The tests held up: not one failure came from a check rejecting correct work. The faults are where we found problems.

Most failures in the sample involve one fault type: a read that returns plausible but outdated data, such as an old revision of a document or a stock record from before a delivery. Our rules require that the true data is always reachable some other way, and it was in every task. What the audit showed is that reachable is not enough. The agent needs a reason to go looking.

Where an agent had a reason, its failure was fair. Some agents were told by a runbook which revision of a document is current, saw that the document they got was older, and used it anyway. One agent noticed that the changelog gave a limit of 200 and the page it read said 500, picked 500, and reported success. In one build task, the code used one debug flag and the build doc the agent read named another; the agent changed the build to match the doc. Those are real mistakes, and the benchmark should count them.

Where nothing pointed anywhere, the failure was not fair. In the Rust build task nobody passed, the build instructions say to update one dependency at a time. Under faults, every agent read a version that says to refresh all of them, and nothing else in the repository says otherwise. Every agent followed the version it read and failed the same check; for 12 of the 15, it was the only one of 85 checks that failed. We found nine tasks with this problem.

## What it changes

The share of failed trials where the agent still reported success is lower than we published. Counting only the agent's own mistakes, our estimate is about 46% on Track S instead of 79%, and about 64% on Track N instead of 91%. The sample is small, so the true values could be roughly 34% to 57% on Track S and 47% to 71% on Track N. Agents still claim success on most of their real failures. They do it less often than our numbers said.

The audit also found a gap in our own records. For 26 of the 80 trials, the repository kept the score but not the test output that explains it, because the list of files we save left those logs out. Without the archives we could not have done this audit.

Nothing in the M6 results changes today. Our next step is a plan to fix the nine tasks so each one gives the agent something to notice, to re-score them, and to correct the success-reporting figure on this site and in the paper. We will also save every test log from now on. The full report, with every label and the evidence behind it, is in the repository: [reports/2026-11-26-failure-audit.md](https://github.com/davila7/chaos-monkey-coding-agents/blob/main/reports/2026-11-26-failure-audit.md).

The guide was right. We should have read our failures sooner.
