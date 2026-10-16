# Splitting tally/reports.py into a package

`tally/reports.py` holds loading, aggregation, every output format, the
formatting helpers and the command line in one module of about 2,500 lines.
This guide fixes the layout it is split into and the rules the split must
follow. Every rule below is checked when the change is reviewed; a split that
breaks one of them is not accepted, even if the tests pass.

The split is a move of code, not a rewrite. Nothing a caller can observe may
change.

## 1. Target layout

The module becomes the package `tally/reports/`. These are the only modules
and sub-packages allowed directly inside it:

| Name | Layer | Holds | Form |
|---|---|---|---|
| `__init__.py` | 6 | the public API, re-exported (section 5) | single module |
| `errors.py` | 0 | exception classes | single module |
| `tables.py` | 0 | fixed data: the version string, width limits, locale, currency and exchange-rate tables | single module |
| `state.py` | 0 | process-wide settings, caches and counters, and the functions that read and change them | single module |
| `system.py` | 0 | access to the clock, the terminal and input files: the patch points (section 7) | single module |
| `formatting` | 1 | turning numbers, money, dates and text into strings; escaping | module or package |
| `model` | 1 | data classes for records, sections, options and reports | module or package |
| `loading` | 2 | reading exports into records, parsing, plausibility checks | module or package |
| `aggregate` | 3 | metrics, grouping, report sections and building a report | module or package |
| `renderers` | 4 | the output formats (section 4) | package |
| `cli` | 5 | the `tally report` command line | module or package |

"Module or package" means either `name.py` or a directory `name/` with an
`__init__.py` and any modules you choose; every module inside a sub-package
has the layer of the sub-package. "Single module" means `name.py`, never a
directory. There is no `__main__.py` in `tally/reports/`.

The "Holds" column says where code belongs by what it does. When a helper is
used by code in several layers, it goes in the lowest layer that uses it,
whatever section of the old file it sat in. The old file was not written with
layers in mind; its section banners are not the target layout.

`tally/reports.py` itself is removed once the package exists (a package and a
module of the same name cannot both be imported).

## 2. Size

No `.py` file in `tally/reports/`, at any depth, is longer than **400 lines**.
Every line counts: code, comments, docstrings and blank lines.

## 3. Imports

1. **Layers.** A module may import from modules in its own layer or in a lower
   layer, never from a higher one. Importing the package itself
   (`import tally.reports`, `from tally.reports import x` where `x` is not a
   submodule, or a relative `from .. import x` that resolves to the package)
   counts as importing layer 6.
2. **No cycles.** The import graph of the package's modules has no cycle.
   Every import statement counts, wherever it appears: at module level, inside
   a function or method, or under a condition. Moving an import into a function
   does not remove it from the graph. `from a.b import c` is an import of
   `a.b.c` when that is a module, and of `a.b` otherwise.
3. **Static only.** No `importlib`, no `__import__`.
4. **Self-contained.** Modules of `tally/reports/` import nothing from the rest
   of the `tally` package. Other `tally` modules may import from
   `tally.reports` as before.

## 4. Renderers

1. `renderers/base.py` holds the `Renderer` base class and the registry
   (registration, aliases, lookup).
2. Each renderer class lives in `renderers/<name>.py`, where `<name>` is the
   name it is registered under, which is not always the class name. A module
   may hold helpers used only by its renderer.
3. Importing `tally.reports` registers every renderer and every alias, as it
   does today.
4. Registration order is behavior: `available_formats()`, `--list-formats` and
   `--format all` list renderers in the order they were registered, and that
   order must not change.

## 5. Public API

1. Every **public name** of the old module stays importable from
   `tally.reports`: every top-level name it defines (function, class or
   assignment) that does not start with an underscore, whether or not it is
   listed in `__all__`. Names the old module only imported (`json`, `Decimal`)
   are not part of the API.
2. Each public name keeps its kind and, for functions and classes, its call
   signature: parameter names, kinds and fallback values (`x=...`). Constants keep their
   values.
3. `tally.reports.__all__` stays exactly as it is, in the same order.
4. `tally/reports/__init__.py` contains only a docstring, import statements and
   the `__all__` assignment. No functions, classes or other statements.
5. Nothing is renamed and nothing is deleted, even code that looks unused. Each
   function and class of the old module is defined in exactly one module of
   the package: no copies, no wrappers with the same name.

## 6. Private names

1. Names that start with an underscore are private. `tally.reports` does not
   re-export them: after the split, `tally.reports.<private name>` is an
   attribute error for every private name of the old module.
2. Code elsewhere in the repository that imports a private name from
   `tally.reports` imports it from the module that now defines it.

## 7. State and patch points

1. **Module state.** Some module-level variables are rebound after import by
   functions that declare them `global`. Each such variable keeps exactly one
   home: it is assigned at top level in exactly one module. Every other module
   reads it through its home module at call time (`state._counter`), never
   with `from ... import _counter`: that copies the value at import time, and
   later changes would not be seen.
2. **Patch points.** Tests replace these functions with `unittest.mock.patch`.
   After the split each one is defined in `system.py`, and every caller looks
   it up through the module at call time (`system._now()`), so that patching
   the canonical location affects every caller.

   | Patched before the split | Canonical location after the split |
   |---|---|
   | `tally.reports._now` | `tally.reports.system._now` |
   | `tally.reports._terminal_width` | `tally.reports.system._terminal_width` |
   | `tally.reports._open_source` | `tally.reports.system._open_source` |

3. **Tests.** The only change allowed under `tests/` is updating `mock.patch`
   targets to the canonical locations above. Reviewers run their own copy of
   the tests with those targets.

## 8. Behavior

1. For any input files and any options, `python -m tally ...` writes the same
   bytes to stdout and to stderr and exits with the same status as before the
   split. This includes warnings, errors and usage messages.
2. Every value the public API returns, and every exception it raises, stays
   the same. That includes the quirks: do not fix bugs, reword messages or
   tidy up behavior while moving code.
3. Text that is derived from a module's name, such as a logger name, does not
   change. Moving code into another module changes `__name__`; where the old
   code used it, keep the value it had.
4. A parameter's fallback value (`def f(x=VALUE)`) is evaluated once, when the
   `def` statement runs. Keep what each one evaluates to.
5. `python -m unittest discover -s tests -t .` passes from `/app`.

## 9. Checking your work

The old module is the reference. Before you move anything, keep a copy of it
outside the package and record what the command line prints for a range of
inputs and options (`samples/` has exports; `docs/cli.md` lists the options),
on stdout and stderr, with `SOURCE_DATE_EPOCH` and `COLUMNS` set so that the
output does not depend on the clock or the terminal. Compare after each step.
Reviewers compare against the old module on other exports and options.
