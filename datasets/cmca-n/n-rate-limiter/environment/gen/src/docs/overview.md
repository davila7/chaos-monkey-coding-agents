# frontdoor: overview

`frontdoor` is the admission layer of the edge: it decides, for each incoming
request, whether it is routed, authenticated and passed upstream, and what the
edge answers otherwise. In production it runs inside the edge proxy. This
repository runs the same code offline: `replay` reads request traces captured
at the edge and writes the decision taken for every request, so a change can
be checked against real traffic before it ships.

    python -m frontdoor check  --config PATH
    python -m frontdoor routes --config PATH
    python -m frontdoor replay --config PATH --out DIR TRACE...

The package uses only the Python standard library (Python 3.12).

| Note | Covers |
|---|---|
| `config.md` | the configuration file and every section it may hold |
| `pipeline.md` | the stages a request passes through, and how replay runs them |
| `traces.md` | the trace file format and what is known about the captured traffic |
| `output.md` | `decisions.jsonl` and `summary.json` |
| `conventions.md` | how the code is organised and how to add a section or a stage |
| `ratelimit.md` | the rate limiting stage (release 2.7) |

## Repository layout

    frontdoor/          the package
      cli.py            the three commands
      replay.py         runs the stages over traces and writes the output
      timeutil.py       trace timestamps
      config/           loading the configuration; one module per section
      http/             headers, paths, the access log client address
      routing/          route matching
      stages/           one module per stage, and the stage list
      trace/            reading trace files
      output/           decisions.jsonl and summary.json
    configs/            configurations of the edge nodes
    traces/             captured traffic, one file per capture window
    docs/               these notes
    tests/              unit tests (python -m unittest discover -s tests -t .)

## Releases

- 2.7 (planned): rate limiting (`ratelimit.md`). `configs/edge.toml` already
  carries the limits that production will run with, so `check` and `replay`
  refuse it until the stage exists.
- 2.6: `[upstream] timeout`; route `status`.
- 2.5: `routes` command; public routes.
- 2.4: `summary.json` gets per-route counts.
