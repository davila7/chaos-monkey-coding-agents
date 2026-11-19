## Summary

<!-- What changes and why. Name the DECISIONS.md entry (D-xxxx) when the change departs from SPEC.md. -->

## Checks

- [ ] `pnpm build && pnpm typecheck && pnpm test && pnpm lint` and `uv run pytest` pass
- [ ] Changed tasks bump their `version` (CONTRIBUTING.md, Task versions) and pass `cmca_harbor.validate`
- [ ] Every number in a changed document comes from a committed artifact
- [ ] No secrets, no banned words in agent-visible files (SPEC 7.2)
- [ ] No model runs, or the run has an approved cost estimate (SPEC 20)
