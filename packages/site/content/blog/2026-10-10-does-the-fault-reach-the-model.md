---
title: Does the fault reach the model?
date: 2026-10-10
summary: How faults get into a coding agent, why we test delivery before we test agents, and what the first conformance batch found.
---

This is the first post in a series about building Chaos Monkey for Coding Agents in the open. There are no benchmark results yet. This post covers the step that has to come before them.

## What the benchmark measures

Coding agents call tools all day: read a file, edit it, run a command, query a service. In real work those calls fail. A file is locked, a request times out, a command reports an error after it already changed something.

The benchmark makes those failures happen on purpose, in a controlled and repeatable way, and watches what the agent does next. Does it retry, find another way, give up, or claim success anyway? Same task, same seed, same failures, different harness.

## How a fault gets in

![A tool call passes from the model through the harness to the injector. The injector asks a seeded schedule whether to fail this call, logs the decision, and either lets the real tool run or returns a replaced result.](/blog/fault-path.svg)

The harness is the program that runs the agent loop (Claude Code, Pi, and others). We do not modify it. Each harness has an official extension point, and the injector plugs into it.

For every tool call, the injector asks a seeded schedule one question: fail this call or not, and how. The answer depends only on the seed and the call, so a rerun gets the same faults. Some fault types stop the call before the tool runs (permission denied, timeout). Others let the tool run and then replace what comes back (an empty file, cut-off output, plausible but wrong data, or an error after the change was already made).

Every decision is written to a log, so the analysis can later match each fault with what the agent did about it.

## Why delivery comes first

A benchmark like this has a quiet way to be wrong. If the injector decides to fail a call but the failure never reaches the model, the trial looks like a clean success. Count enough of those and a harness looks robust when it was simply never tested.

So before any agent is scored, every harness goes through a conformance suite. It asks one narrow question per fault type and tool: when we inject this, does the model actually see it?

![A probe task makes one targeted call. One fault is forced on that call. The probe runs three times, and each run is checked for a logged decision and for the payload in what the model saw. Passing cells can be scheduled; failing cells become gaps that are never scheduled.](/blog/conformance.svg)

## The first conformance batch

The first batch ran on 2026-10-10 on a maintainer's machine with Harbor 0.24.0, Claude Code 2.1.289 and Pi 1.0.3, three runs per probe.

- Pi 1.0.3: 17 of 17 probes passed.
- Claude Code 2.1.289: 15 of 22 probes passed.

The failures were more useful than the passes.

**An empty result cannot be shown for Write and Edit in Claude Code.** For those two tools Claude Code prints a fixed success line no matter what result the extension returns. This is how the extension API works, not a bug in the injector. The proposal ([D-0017](https://github.com/davila7/chaos-monkey-coding-agents/blob/main/DECISIONS.md)) is to record those cells as gaps that the schedule never picks, rather than dropping the fault type everywhere.

**Search tools were not there.** Claude Code 2.1.289 exposes no Grep, Glob or LS tool in the session, so the agent searches through the shell. Search and list faults can only reach it through shell commands on this version. The capability file will record that mapping.

**An empty file still reported its real length.** When the injector emptied a Read result, Claude Code still printed the original line count, which gives the trick away. The injector now rewrites that count too. This fix has not been re-run yet.

**A misconfigured injector looked like a clean run.** In an early trial the injector received a config it could not use. It made no decisions and logged nothing, so the trial looked fault-free. It now writes an explicit error record in that case, so a broken setup can no longer pass as a clean trial.

## What this does not cover yet

This batch checked two things: the injector logged its decision, and the payload reached what the model saw. It did not check side effects on disk, text added by the harness, injector latency, or what happens when the injector itself crashes. Those checks come next.

The raw logs for this batch are still on the machine that ran them. The numbers above are as reported in the verification records [V-01](https://github.com/davila7/chaos-monkey-coding-agents/blob/main/docs/verification/V-01.md) and [V-10](https://github.com/davila7/chaos-monkey-coding-agents/blob/main/docs/verification/V-10.md), which mark them the same way. The capability files will be generated and committed from the rerun.

## Next

The next step is a smoke run: Claude Code on three pilot tasks, once with no faults and once under the moderate profile. It exists to prove the pipeline works end to end, from trial to analysis to this site. It will appear on the results page labeled as a smoke run, with no ranking.
