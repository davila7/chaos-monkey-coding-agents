# Renderer plugins

A renderer turns formatted addresses into one output document. orbis.postal
has three built-in renderers (`text`, `oneline`, `json`); every other
renderer is a plugin found through package metadata.

## 1. The entry point group

Plugins are entry points in the group `orbis.postal.renderers`. The entry
point name is the renderer name used with `--renderer`; the object is a
class derived from `orbis.postal.render.Renderer`:

    [project.entry-points."orbis.postal.renderers"]
    cn22 = "orbis.customs.cn22:Cn22Renderer"

orbis-postal itself registers the two renderers of `orbis.labels` (`sheet`
and `envelope`) this way, so they are found exactly like third-party ones.

A built-in name cannot be replaced by a plugin: when a plugin uses the name
`text`, `oneline` or `json`, the built-in renderer is used. When two
distributions on the path register the same name, the one found first on
`sys.path` wins.

## 2. Loading

`orbis-postal renderers` lists every renderer without importing any plugin:
one line per renderer, sorted by name, with three tab-separated fields:

    <name>  <origin>  <module>:<class>

The origin is `built-in` or the name of the distribution that registers the
entry point, as written in its metadata.

A plugin is imported only when it is used. If its module cannot be imported
or the object is not a renderer class, the command fails with exit status 2
and the message

    orbis-postal: error: renderer '<name>' could not be loaded: <exception type>: <message>

The 2.x entry point `orbis.postal.cli:main` predates plugins and only knows
the built-in renderers (CHANGELOG.md, 3.0.0).

## 3. The orbis namespace

`orbis` is a native namespace package (PEP 420): a directory without
`__init__.py`, shared by every Orbis distribution. orbis-postal provides
`orbis.postal` and `orbis.labels`; other distributions add their own
packages, for example a customs plugin that ships `orbis/customs/` and
registers a `cn22` renderer.

Python merges the `orbis` directories of every path entry only while none of
them is a regular package. A single `orbis/__init__.py` anywhere on the
path turns `orbis` into an ordinary package rooted in that one directory,
and the packages of every other Orbis distribution stop being importable.
That is why no Orbis distribution ships `orbis/__init__.py`.

## 4. Writing a plugin

- Derive from `orbis.postal.render.Renderer`, set `name` and
  `description`, and implement `render(items)`, which receives
  `(address, lines)` pairs in input order and returns the whole output.
- `self.options.origin` is the sender country given with `--from`, or
  `None`.
- Read package data with `importlib.resources`, never with paths relative to
  the module file, so the plugin also works from a zip or an unusual
  install layout.
- Raise `orbis.postal.errors.DataError` when a data file the plugin needs is
  missing; the command line turns it into exit status 3.
