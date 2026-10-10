# Chaos Monkey for Coding Agents: implementation rules

SPEC.md is the source of truth. Propose changes through DECISIONS.md entries. Never deviate silently.

## Operating rules

1. Plan first. At the start of each milestone, write a plan in DECISIONS.md (scope, files to create, risks, verification items to close) and wait for the owner's approval before executing.
2. Never delete files unless the owner explicitly asks.
3. Verify before building. For every third-party interface (Harbor, Claude Code mods, Codex hooks, Antigravity hooks, Pi extensions, OpenCode v2 plugins, fx, MCP SDK), read the current official documentation and test against the pinned binary inside a container. Record evidence in docs/verification/V-xx.md. When documentation and observed behavior disagree, observed behavior wins and both are recorded.
4. Never fabricate results, benchmarks, citations, or examples. Every number in any document must come from a committed artifact.
5. No model-API runs beyond conformance probes without the owner's approval of a cost estimate (SPEC section 20).
6. All code, comments, documentation, and configuration values in English. TypeScript by default. Python only under python/ for Harbor integration and analysis.
7. No boilerplate comments. Comment only non-obvious decisions. Do not create README files beyond the documentation set in SPEC section 15.1.
8. Every package has tests. Property tests for fault-engine. Snapshot tests for analysis. CI must be green before a milestone is marked done.
9. Record every non-trivial decision in DECISIONS.md: date (YYYY-MM-DD), context, decision, alternatives considered, consequences.
10. Reports and run logs use YYYY-MM-DD filename prefixes.
11. Never use the banned word list (SPEC section 7.2) in any agent-visible file, path, environment variable, or payload. The lint rule enforces this; do not disable it.
12. Never mutate shell arguments. Never run trials outside containers. Never commit secrets.
13. Documentation style: direct and technical, no marketing language, no emojis, no em dashes or en dashes.

## Definition of done

A milestone is done when every acceptance criterion in SPEC section 19 is met, the related verification items are closed, and the owner has reviewed the milestone summary in DECISIONS.md.

## Project links

- Results site (production): https://chaos-monkey-coding-agents.vercel.app. Source in `packages/site`; Vercel deploys `main` with Root Directory `packages/site`.
