# Testing

## 1. Unit tests

1.1 The tests live in `tests/` and use `unittest` only. From the project root:

    python -m unittest discover -s tests -t .

runs them in the order `unittest` picks (modules, classes and methods sorted
by name), in one process, with whatever `PYTHONHASHSEED`, `TZ` and clock the
shell has.

1.2 Every test must pass alone and in any company: in any order, under any
hash seed, in any timezone and on any date. Tests do not use module or class
fixtures (`setUpModule`, `setUpClass`); each test builds what it needs.

1.3 Fixtures are under `tests/fixtures/`. Tests write files only in their
own temporary directories.

## 2. The CI runner

2.1 `tools/ci.py` runs the tests the way CI does. CI starts it on every push,
on one of six runners. Each runner keeps the timezone of the site it runs at:

| Runner | `TZ` |
|---|---|
| `ci-01` | `UTC` |
| `ci-02` | `America/Los_Angeles` |
| `ci-03` | `Europe/Berlin` |
| `ci-04` | `Asia/Tokyo` |
| `ci-05` | `Pacific/Auckland` |
| `ci-06` | `America/Sao_Paulo` |

2.2 The runner collects every test id, sorts them and shuffles them with a
seed, then runs all of them in that order in one child process, one at a
time. A test therefore runs after a random selection of other tests in the
same process.

2.3 The child gets a random `PYTHONHASHSEED`, the runner's `TZ`,
`STOCKROOM_NOW` set to the time the run started (`overview.md` 4), and its
own empty temporary directory (`TMPDIR`), removed after the run.

2.4 The header of a run names the run id, the runner and the release under
test, and prints a replay line that repeats the run with the same seed, hash
seed, timezone and clock:

    python tools/ci.py --seed 551204 --hash-seed 2871120944 --tz America/Los_Angeles --now 2027-01-29T18:04:11Z

`--order sorted` and `--order reverse` replace the shuffle. `-k TEXT` keeps
the tests whose id contains `TEXT` (several `-k` may be given) and runs them
in the order they have in the full run. `--list` prints the order and runs
nothing. Run `python tools/ci.py --help` for the rest.

2.5 Each test prints one line, `ok`, `FAIL`, `ERROR` or `skip`, with its id.
After the last test the runner prints a `---- FAIL:` or `---- ERROR:` block
with the traceback of each test that did not pass, then a `result:` line. A
run cancelled by an operator (Ctrl-C, or a cancel in the CI interface) stops
in the test that was running; that test is reported as an `ERROR` ending in
`KeyboardInterrupt`, and the last line reads `run cancelled after ...`.

## 3. CI logs

3.1 The output of recent CI runs is kept in `logs/ci/`, one file per run,
named `YYYY-MM-DD-run-ID.log` after the start date (UTC) and the run id.

3.2 The logs are the runner's output as it was printed; nothing is added or
removed.

## 4. Triage of intermittent failures

4.1 A test that fails in some runs and passes in others is intermittent. The
cause is a defect in the package or in the test, not bad luck. Before a
failure is filed, it is traced to its root cause: the line of code that is
wrong.

4.2 One root cause can fail several tests, and one test can fail for more
than one root cause (in different runs). A failure that does not come from a
defect in the current code is not filed.

4.3 Each root cause is filed under one of these classes:

| Class | The result depends on |
|---|---|
| `shared-state` | a module-level or class-level mutable object (not a cache) that one call changes and a later call reads |
| `cache-key` | a cache whose key leaves out part of the input, so a call gets a result stored for different input |
| `hash-order` | the iteration order of a set or frozenset, which changes with `PYTHONHASHSEED` |
| `clock` | the current date or time, in the same way in every timezone |
| `timezone` | the local timezone of the process |
| `temp-file` | a file path outside the caller's own directory that two writers, or a writer and a file left behind, can share |
| `float-rounding` | binary floating point where decimal arithmetic is needed |
| `thread-race` | the timing of threads or processes running at the same time |
| `resource` | the speed, memory or disk of the machine |
| `network` | a network service or name lookup |

4.4 Fixes go into the package. A test is changed only when the test itself is
wrong; editing a test so that it no longer hits a defect hides the defect.
