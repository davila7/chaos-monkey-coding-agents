"""The packaging defects of the shipped tree, as edits to the correct tree in src/.

apply(root, ids) applies the listed defects to a copy of the correct tree.
"""

from __future__ import annotations

from pathlib import Path

# id: list of (path, old text, new text); old None means the file is created.
BUGS: dict[str, list[tuple[str, str | None, str]]] = {
    # PEP 639 license keys; setuptools 66 rejects both.
    "license": [
        ("pyproject.toml", 'license = {text = "MIT"}\n', 'license = "MIT"\nlicense-files = ["LICENSE"]\n'),
    ],
    # The attr names a module attribute that does not exist: the build fails.
    "version-attr": [
        ("pyproject.toml", 'version = {attr = "orbis.postal._version.__version__"}\n', 'version = {attr = "orbis.postal.version"}\n'),
    ],
    # A second, stale version in the package: --version disagrees with the metadata.
    "version-literal": [
        ("src/orbis/postal/__init__.py", "from orbis.postal._version import __version__\n", '__version__ = "3.1.4"\n'),
    ],
    # A leftover orbis/__init__.py from 2.x with plain package discovery; the
    # wheel ships orbis/__init__.py. Removing only the file empties the wheel.
    "namespace": [
        ("src/orbis/__init__.py", None, ""),
        (
            "pyproject.toml",
            'include = ["orbis.postal*", "orbis.labels*"]\nexclude = ["orbis.postal._maint*"]\nnamespaces = true\n',
            'include = ["orbis*"]\nnamespaces = false\n',
        ),
    ],
    # Excluding *.csv (meant for tools/timings) drops the abbreviation tables
    # and the CSV fixture from the sdist, so the release wheel lacks the tables.
    "manifest-csv": [
        ("MANIFEST.in", "prune tools/timings\nglobal-exclude *.py[cod]\n", "global-exclude *.py[cod] *.csv\n"),
    ],
    # Formats sit one directory deeper than the glob; no drafts exclusion yet.
    "formats-glob": [
        ("pyproject.toml", '"data/formats/*/*.toml"', '"data/formats/*.toml"'),
        ("pyproject.toml", '\n[tool.setuptools.exclude-package-data]\n"orbis.postal" = ["data/formats/_drafts/*"]\n', ""),
    ],
    # The console script runs the 2.x entry point, which never loads plugins.
    "console-script": [
        ("pyproject.toml", 'orbis-postal = "orbis.postal.commands:main"\n', 'orbis-postal = "orbis.postal.cli:main"\n'),
    ],
    # The group name the code looks up is plural.
    "entry-group": [
        ("pyproject.toml", '[project.entry-points."orbis.postal.renderers"]\n', '[project.entry-points."orbis.postal.renderer"]\n'),
    ],
    # The SVG templates of orbis.labels are not package data.
    "templates": [
        ("pyproject.toml", '"orbis.labels" = ["py.typed", "templates/*.svg"]\n', '"orbis.labels" = ["py.typed"]\n'),
    ],
    # The package needs tomllib (3.11).
    "requires-python": [
        ("pyproject.toml", 'requires-python = ">=3.11"\n', 'requires-python = ">=3.8"\n'),
    ],
}

ALL = list(BUGS)


def apply(root: Path, ids: list[str]) -> None:
    for bug_id in ids:
        for rel, old, new in BUGS[bug_id]:
            path = root / rel
            if old is None:
                if path.exists():
                    raise SystemExit(f"{bug_id}: {rel} already exists")
                path.write_text(new, encoding="utf-8")
                continue
            text = path.read_text(encoding="utf-8")
            if text.count(old) != 1:
                raise SystemExit(f"{bug_id}: expected one match in {rel}")
            path.write_text(text.replace(old, new, 1), encoding="utf-8")
