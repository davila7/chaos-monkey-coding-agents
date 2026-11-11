# Triage

How a wrong value in the state is traced to its cause.

## 1. Where to start

The audits (`operations.md` 6) say which values are wrong at a few times. The
snapshots say what every run wrote, and the scheduler log says what each run
loaded and read. A replay (`operations.md` 3) shows what a job writes for a
given input, so a run whose snapshot differs from what the rules give for its
input can be found, and so can the code that makes it differ.

## 2. Things that look wrong and are not

- A run of an earlier release wrote what that release did. Check
  `logs/deploy.log` and the `version` of the run.
- Operator corrections (`operations.md` 5).
- A run that ended with exit status 1 wrote nothing.
- A value that is wrong in a snapshot was not necessarily made wrong by the
  run that wrote it: it may come from the state the run loaded.

## 3. Cause classes

| Class | Meaning |
|---|---|
| `lost-update` | A run saves a state built on a revision that is no longer the latest, so the changes written in between are lost |
| `retention` | Data is kept for a shorter or longer time than documented |
| `time-compare` | Times are compared as text, or in a way that depends on their offsets, instead of as instants |
| `rounding` | An amount or a duration is rounded the wrong way |
| `idempotency` | A job applies the same input twice where its own check should stop it |
| `capacity` | A count goes past a documented limit, or a bike is lost or gained |
| `timezone` | A time is converted to the wrong zone, or a local time is taken as UTC |
| `parsing` | A field of a feed record is read wrongly |
| `ordering` | Records or moves are applied in the wrong order |
