# Security

## Reporting a vulnerability

Report privately through GitHub: [open a private security advisory](https://github.com/davila7/chaos-monkey-coding-agents/security/advisories/new). Do not open a public issue.

In scope:

- The injectors, the MCP fault proxy, the mock services, the responses bridge and the Harbor agents in this repository, in particular anything that lets a trial escape its container, reach the host, or mutate a shell argument.
- A secret or personal data found in committed evidence (`results/`, `docs/verification/`, `reports/`). Name the file path; do not quote the secret.
- A way to read a task's tests, solution or canary from inside the agent container.

Supported versions: `main` and the latest release tag (currently `m6-2026-11-18`).

Expect an acknowledgement within 7 days. Fixes land on `main`, and `CHANGELOG.md` records them once disclosed.

## Safety findings about a harness

Behavior found during runs that matters for safety (destructive actions after a fault, credential exposure, data loss) is reported privately to the harness vendor at least 14 days before publication, and the disclosure date is recorded in `CHANGELOG.md` (SPEC 15.3). If you find such behavior in the published trajectories, report it through the private advisory above, not in a public issue.
