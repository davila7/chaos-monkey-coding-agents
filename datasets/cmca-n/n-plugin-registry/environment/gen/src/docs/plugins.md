# Format plugins

`xport/formats.py` holds every output format in one module: a table of names,
a table of options, and a set of functions that each branch on the format
name. Adding a format means touching most of them. This document defines what
replaces it: a package `xport/formats/` with a registry and one plugin module
per format, and the interface a plugin implements. It is the contract for the
move and for every format added after it.

The move changes structure only. For every dataset, format, alias and option,
`xport` writes the same bytes to standard output and standard error and exits
with the same status as `xport/formats.py` does today (section 6).

## 1. Terms

- **Format**: a way of writing a table, such as `csv`. It has one canonical
  name and zero or more aliases.
- **Plugin**: a class that implements one format, and the module it lives in.
- **Registry**: the code that finds plugins, keeps them by name and runs an
  export.
- **Invoked name**: the format name exactly as the caller passed it, before
  any case folding or trimming. `-f CSV`, `-f csv` and `-f " csv"` all select
  the same plugin, with three different invoked names.

## 2. Layout

```
xport/formats/
  __init__.py     imports and __all__ only (section 5)
  base.py         Format, Option, Context and the three error classes
  registry.py     register(), discovery, lookup and the export entry points
  common.py       helpers shared by two or more plugins (optional)
  <name>.py       one plugin module per format, named after its canonical name
```

1. `xport/formats.py` is removed. A module and a package of the same name
   cannot both be imported.
2. Each built-in format lives in `xport/formats/<name>.py`, where `<name>` is
   its canonical name: `csv.py`, `tsv.py`, `jsonl.py`, `fixed.py`,
   `markdown.py`, `html.py`, `xml.py`, `sql.py`. A plugin module holds exactly
   one registered format and any helpers only that format uses.
3. A plugin module does not import another plugin module. Code that two
   plugins need goes in `common.py`.
4. `base.py`, `registry.py`, `common.py`, `__init__.py`, any module of
   `xport/formats/` whose name starts with `_`, and every module outside
   `xport/formats/` (`xport/cli.py`, `xport/dataset.py`, ...) do not mention
   any format by name: no string constant in them is equal to a canonical
   name or an alias, and none branches on which format is running.
   Format-specific behavior lives in the plugin. Docstrings are not checked.
5. The same holds for plugin modules with respect to other formats: a plugin
   module may compare against its own name and aliases, never another
   format's.

## 3. The plugin interface

`xport/formats/base.py` defines the following. Plugins import them from
there.

### 3.1 Format

A plugin is a subclass of `Format` with these class attributes:

| Attribute | Type | Meaning |
|---|---|---|
| `name` | `str` | canonical name |
| `aliases` | `tuple[str, ...]` | other names; may be empty |
| `order` | `int` | position in listings (section 4.4) |
| `summary` | `str` | one line, shown by `xport formats` |
| `options` | `tuple[Option, ...]` | the options the format takes, in the order they are checked and listed |

and two methods:

- `check(self, ctx)`: called after every option has been converted
  (section 4.5), before anything is written. It checks options against each
  other and raises `OptionError` with the full message when they do not fit.
  The base class version does nothing.
- `write(self, table, ctx)`: writes the whole table to `ctx.out`. `table` is
  an `xport.dataset.Table`: `table.name`, `table.columns` (each with `name`,
  `type` and `scale`) and `table.rows` (tuples of Python values, `None` for a
  missing value).

The registry makes one instance of each registered class and uses it for
every export.

### 3.2 Option

`Option(name, kind, default=None, choices=(), low=None, high=None)`, a frozen
dataclass. `default` is the value the plugin receives when the option is not
given; it is used as is, not converted. Kinds:

| Kind | Accepted text | Value |
|---|---|---|
| `bool` | `true yes on 1 false no off 0`, any case | `bool` |
| `int` | optional sign and ASCII digits; checked against `low` and `high` when set | `int` |
| `char` | one character, or `tab`, `\t` (two characters) or `space` | `str` of length 1 |
| `choice` | one of `choices`, exact case | `str` |
| `name` | a letter or `_`, then letters, digits, `_`, `.` or `-` | `str` |
| `text` | anything, including the empty string | `str` |

### 3.3 Context

`Context`, a frozen dataclass passed to `check` and `write`:

| Field | Meaning |
|---|---|
| `invoked` | the invoked name (section 1) |
| `options` | dict with every option of the format: the converted value when given, `default` otherwise |
| `given` | frozenset of the option names the caller gave |
| `out` | the text stream to write to |

`given` exists because some formats treat "given" and "left at the default"
differently even when the values are equal. `invoked` exists because a format
may behave differently under one of its aliases; the format reference
(`docs/formats.md`) says where.

### 3.4 Errors

`OptionError` and `UnknownFormatError` (both subclasses of `ValueError`) and
`RegistryError` (a subclass of `Exception`).

## 4. The registry

`xport/formats/registry.py`.

### 4.1 Registration

`register` is a class decorator. Applied to a `Format` subclass it makes one
instance, registers its name and every alias, and returns the class
unchanged.

Names and aliases are lower case: a letter, then letters or digits. Anything
else raises `RegistryError` with the message
`format name '<key>' in <module> is not a valid name`, where `<module>` is the
dotted module name of the class.

### 4.2 Discovery

Plugins are found, not listed. The first call to any registry function that
needs the formats (`lookup`, `resolve`, `list_formats`, `export`,
`export_text`) imports every plugin module of the `xport/formats/` directory
once, in ascending order of module name. A plugin module is any `.py` module
directly in that directory whose name does not start with `_` and is not
`base`, `registry` or `common`. Sub-packages are ignored. `discover()` runs
the same step explicitly; calling it again does nothing.

So adding a format is adding one file: drop `<name>.py` with a registered
`Format` subclass into `xport/formats/`, and `xport formats`, `xport export -f
<name>` and the error messages that list formats pick it up. Nothing else is
edited.

### 4.3 Name collisions

A name or alias may be claimed by one format only. When a plugin claims a key
that an earlier registration already holds (as a name or as an alias),
registration raises `RegistryError` with the message

```
format name '<key>' is claimed by <earlier module> and <later module>
```

The keys of a plugin are checked in order, name first, then aliases; the first
key in conflict is reported. Nothing of the conflicting plugin is registered.
Since discovery imports in name order, `<earlier module>` is the one whose
name sorts first. On the command line a `RegistryError` is printed as
`xport: error: <message>` on standard error, with exit status 70, for every
command that needs the formats.

### 4.4 Lookup and listing

- `lookup(name)` returns the registered `Format` instance for a canonical name
  or alias. The name is trimmed of surrounding white space and compared in
  lower case. An unknown name raises `UnknownFormatError` with
  `unknown format '<invoked name>' (known: <canonical names in listing order, joined by ", ">)`.
- `resolve(name)` returns `lookup(name).name`.
- `list_formats()` returns `(name, aliases, summary)` tuples, one per format,
  in listing order.
- Listing order sorts formats by `order`, then by `name` for equal orders.
  `xport formats`, `list_formats()` and the "known" list of
  `UnknownFormatError` use it. The built-in formats keep the listing they have
  today, with these orders:

| Format | `order` |
|---|---|
| `csv` | 10 |
| `tsv` | 20 |
| `jsonl` | 30 |
| `fixed` | 40 |
| `markdown` | 50 |
| `html` | 60 |
| `xml` | 70 |
| `sql` | 80 |

### 4.5 Options

`export` receives options as `key=value` strings and checks them in three
passes, stopping at the first error:

1. Every string, in the order given: it must contain `=` with a non-empty key
   (the key is trimmed of surrounding spaces, the value is kept as is), or
   `OptionError("option '<string>' is not key=value")`. The key must be an
   option of the format, or
   `OptionError("format '<invoked name>' has no option '<key>' (options: <option names in declared order, joined by ", ">)")`,
   with `none` in place of the list for a format without options. When a key
   is given twice, the last value counts.
2. Every option of the format, in declared order: a given value is converted
   by its kind (section 3.2). Messages, with `<where>` standing for
   `option '<option>' of format '<invoked name>'`:

   | Problem | Message |
   |---|---|
   | bool not recognised | `<where> takes true or false, not '<text>'` |
   | int not a whole number | `<where> takes a whole number, not '<text>'` |
   | int below `low` | `<where> must be at least <low>` |
   | int above `high` | `<where> must be at most <high>` |
   | char not one character | `<where> takes a single character, not '<text>'` |
   | choice not listed | `<where> takes one of <choices joined by "|">, not '<text>'` |
   | name not valid | `<where> takes a name (letters, digits, _ . -), not '<text>'` |

3. `check(ctx)` of the plugin.

Messages name the format by its invoked name, never by its canonical name
unless that is what the caller typed. On the command line an `OptionError` or
`UnknownFormatError` prints `xport: error: <message>` with exit status 2, and
nothing is written to standard output.

### 4.6 Export

`export(table, fmt_name, options=(), out=None)` looks the format up, checks
the options (section 4.5), builds the `Context` and calls `write`.
`export_text(table, fmt_name, options=())` does the same into a string, using
an `io.StringIO(newline="")`.

## 5. Public API

`xport.formats` keeps these names, with the same call signatures:
`export`, `export_text`, `list_formats`, `resolve`, `OptionError`,
`UnknownFormatError`. It adds `register`, `discover`, `lookup`, `Format`,
`Option`, `Context` and `RegistryError`, each also importable from the module
that defines it (`base` or `registry`). `xport/formats/__init__.py` contains
only a docstring, imports and an `__all__` with these thirteen names.

The tables `FORMATS` and `OPTIONS` and the function `parse_options` of the old
module are not kept: each plugin carries its own name, aliases, summary and
options.

## 6. Behavior

1. For every dataset, format name or alias, and option list, `xport export`
   writes the same bytes to standard output and standard error and exits with
   the same status as before. `xport formats` prints the same listing. This
   covers values and situations that `samples/` and `tests/` do not contain.
2. The move is not a clean-up. Where formats differ from each other in how
   they round, escape, quote, pad, order or encode a value, the difference is
   behavior and stays. Shared helpers are shared only where the old code gave
   every caller the same result. The old module is the reference for anything
   this document and `docs/formats.md` leave open.
3. `python -m unittest discover -s tests -t .` passes from `/app` without
   changes to `tests/`.
4. `xport/cli.py` changes only to print `RegistryError` (section 4.3).
   `xport/dataset.py` does not change.

## 7. Example

A format that writes one `name: value` line per cell, as an illustration of
the interface (not one of the built-in formats):

```python
from xport.formats.base import Format, Option, OptionError
from xport.formats.registry import register


@register
class Cards(Format):
    name = "cards"
    aliases = ("card",)
    order = 90
    summary = "one block of name: value lines per row"
    options = (Option("blank", "bool", True), Option("indent", "int", 0, low=0, high=8))

    def check(self, ctx):
        if ctx.options["indent"] and not ctx.options["blank"]:
            raise OptionError(f"format '{ctx.invoked}' cannot indent without blank lines")

    def write(self, table, ctx):
        pad = " " * ctx.options["indent"]
        for row in table.rows:
            for col, value in zip(table.columns, row):
                ctx.out.write(f"{pad}{col.name}: {'' if value is None else value}\n")
            if ctx.options["blank"]:
                ctx.out.write("\n")
```

Saved as `xport/formats/cards.py`, it appears last in `xport formats` and
works with `xport export data.json -f card -o indent=2`.

## 8. Checking the move

Keep a copy of `xport/formats.py` and of the whole `xport` package outside
`/app/xport` before changing anything, and compare the old and new command
lines byte for byte (standard output, standard error, exit status) over the
datasets in `samples/` and over datasets of your own. Reviewers do the same
with datasets, formats, aliases and options you have not seen, and they add a
plugin module of their own to check discovery, listing order, option checks
and name collisions.
