# The request pipeline

## 1. Stages

Each request goes through the stages of `STAGES` in order. A stage either
passes the request on or answers it with a status; the first answer is the
decision, and later stages never see the request.

| Order | Stage | Answers |
|---|---|---|
| 1 | `route` | 404 when no route matches; 405 (with `Allow`) when the route does not take the method |
| 2 | `auth` | 401 (with `WWW-Authenticate`) when the route is not public and the `X-Api-Key` header is missing or unknown |
| 3 | `ratelimit` (release 2.7) | 429 when a limit is exceeded (`ratelimit.md`) |
| 4 | `upstream` | the route's status |

A request answered by an earlier stage does not reach later ones; in
particular, requests answered with 404, 405 or 401 are never counted by the
rate limiting stage.

## 2. The context

`handle(ctx, state)` gets a `Context` with:

- `request`: the request (`traces.md`, section 2): `id`, `ts_ms`, `peer`,
  `method` (upper case), `path`, `headers`;
- `config`: the loaded configuration;
- `route`: the matched route, set by the route stage;
- `tenant`: the tenant name, set by the auth stage, or None (public routes
  without a known key);
- `headers`: the response headers, a dict that stages add to.

## 3. Replay

`replay` loads and checks the configuration, calls each stage's `setup`, then
reads the trace files in the order given on the command line, and each file
line by line, and runs every request through the stages. State kept by a
stage carries over from one trace file to the next. After the last request it
writes `decisions.jsonl` and `summary.json` into the output directory
(`output.md`) and prints `replayed N requests`.
