"""kiln: the in-tree build backend (PEP 517) for this repository.

Reads pyproject.toml ([project] and [tool.kiln]) and writes pure-Python
wheels and gzipped source distributions. Output is reproducible: entries are
sorted and every timestamp is SOURCE_DATE_EPOCH, or 1980-01-01 when that is
not set. docs/kiln.md describes the configuration.
"""

from __future__ import annotations

import base64
import hashlib
import io
import os
import re
import tarfile
import time
import tomllib
import zipfile
from pathlib import Path, PurePosixPath

__all__ = ["build_wheel", "build_sdist", "get_requires_for_build_wheel", "get_requires_for_build_sdist", "KilnError"]

PROJECT_KEYS = {
    "name", "version", "description", "readme", "requires-python", "license", "license-files", "authors",
    "maintainers", "keywords", "classifiers", "urls", "scripts", "gui-scripts", "entry-points",
    "dependencies", "optional-dependencies", "dynamic",
}
TOOL_KEYS = {"source", "version-file", "package-data", "exclude", "sdist-include"}
ALWAYS_SKIPPED = ("__pycache__",)
SKIPPED_SUFFIXES = (".pyc", ".pyo")
VERSION_RE = re.compile(r"""^__version__\s*=\s*["']([^"']+)["']\s*$""", re.M)
NAME_RE = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?$")
EXTRA_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
EP_RE = re.compile(r"^[A-Za-z_][\w.]*(:[A-Za-z_][\w.]*)?$")


class KilnError(Exception):
    """A configuration problem; the message names the key or file."""


# Globs -------------------------------------------------------------------


def glob_to_regex(pattern: str) -> re.Pattern:
    """`*` matches within one path segment (dot files included), `**` matches
    any number of whole segments (zero included), `?` one character."""
    out = []
    parts = pattern.split("/")
    for i, part in enumerate(parts):
        last = i == len(parts) - 1
        if part == "**":
            out.append("(?:[^/]+/)*" if not last else "(?:[^/]+/)*[^/]+")
            continue
        seg = ""
        for ch in part:
            if ch == "*":
                seg += "[^/]*"
            elif ch == "?":
                seg += "[^/]"
            else:
                seg += re.escape(ch)
        out.append(seg + ("" if last else "/"))
    return re.compile("^" + "".join(out) + "$")


def matches(path: str, patterns) -> bool:
    return any(glob_to_regex(p).match(path) for p in patterns)


def walk_files(root: Path) -> list:
    """Every file under root as a POSIX path relative to root, sorted;
    __pycache__ directories and compiled files are never listed."""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in ALWAYS_SKIPPED)
        for f in filenames:
            if f.endswith(SKIPPED_SUFFIXES):
                continue
            out.append(PurePosixPath(Path(dirpath, f).relative_to(root).as_posix()).as_posix())
    return sorted(out)


# Configuration -----------------------------------------------------------


class Project:
    def __init__(self, root: Path):
        self.root = root
        path = root / "pyproject.toml"
        try:
            doc = tomllib.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise KilnError("pyproject.toml not found") from None
        except tomllib.TOMLDecodeError as exc:
            raise KilnError(f"pyproject.toml: {exc}") from None
        self.project = doc.get("project")
        if not isinstance(self.project, dict):
            raise KilnError("pyproject.toml has no [project] table")
        unknown = sorted(set(self.project) - PROJECT_KEYS)
        if unknown:
            raise KilnError(f"[project]: unknown key(s) {', '.join(unknown)}")
        self.tool = doc.get("tool", {}).get("kiln", {})
        unknown = sorted(set(self.tool) - TOOL_KEYS)
        if unknown:
            raise KilnError(f"[tool.kiln]: unknown key(s) {', '.join(unknown)}")
        self.name = self._name()
        self.version = self._version()
        self.source = root / self.tool.get("source", "src")
        if not self.source.is_dir():
            raise KilnError(f"[tool.kiln] source: {self.tool.get('source', 'src')!r} is not a directory")
        self.exclude = list(self.tool.get("exclude", []))

    @property
    def dist_name(self) -> str:
        return re.sub(r"[-_.]+", "_", self.name).lower()

    def _name(self) -> str:
        name = self.project.get("name")
        if not isinstance(name, str) or not NAME_RE.match(name):
            raise KilnError(f"[project] name: invalid {name!r}")
        return name

    def _version(self) -> str:
        dynamic = self.project.get("dynamic", [])
        if "version" in dynamic:
            if "version" in self.project:
                raise KilnError("[project] version is both set and listed in dynamic")
            rel = self.tool.get("version-file")
            if not rel:
                raise KilnError("[project] dynamic version needs [tool.kiln] version-file")
            try:
                text = (self.root / rel).read_text(encoding="utf-8")
            except FileNotFoundError:
                raise KilnError(f"[tool.kiln] version-file: {rel} not found") from None
            m = VERSION_RE.search(text)
            if not m:
                raise KilnError(f"[tool.kiln] version-file: no __version__ = \"...\" line in {rel}")
            version = m.group(1)
        else:
            version = self.project.get("version")
            if not isinstance(version, str):
                raise KilnError("[project] version is missing")
        if not re.match(r"^\d+(\.\d+)*((a|b|rc)\d+)?(\.post\d+)?(\.dev\d+)?$", version):
            raise KilnError(f"version {version!r} is not a valid version")
        return version

    # Contents ---------------------------------------------------------

    def packages(self) -> list:
        """Dotted names of the import packages under source: directories with
        an __init__.py whose parent directories are packages too."""
        out = []
        for dirpath, dirnames, filenames in os.walk(self.source):
            dirnames[:] = sorted(d for d in dirnames if d not in ALWAYS_SKIPPED)
            rel = Path(dirpath).relative_to(self.source)
            if rel == Path("."):
                continue
            if "__init__.py" not in filenames:
                dirnames[:] = []
                continue
            out.append(".".join(rel.parts))
        return sorted(out)

    def wheel_files(self) -> list:
        """(path in the wheel, absolute source path), sorted by wheel path."""
        packages = self.packages()
        chosen = {}
        for pkg in packages:
            pdir = self.source.joinpath(*pkg.split("."))
            for f in sorted(os.listdir(pdir)):
                if f.endswith(".py") and (pdir / f).is_file():
                    rel = f"{pkg.replace('.', '/')}/{f}"
                    if not matches(rel, self.exclude):
                        chosen[rel] = pdir / f
        data = self.tool.get("package-data", {})
        if not isinstance(data, dict):
            raise KilnError("[tool.kiln] package-data must be a table of package = [globs]")
        for pkg, globs in sorted(data.items()):
            if pkg not in packages:
                raise KilnError(f"[tool.kiln.package-data] {pkg!r} is not a package under {self.source.name}/")
            pdir = self.source.joinpath(*pkg.split("."))
            for rel in walk_files(pdir):
                if rel.endswith(".py") or not matches(rel, globs):
                    continue
                wheel_path = f"{pkg.replace('.', '/')}/{rel}"
                if not matches(wheel_path, self.exclude):
                    chosen[wheel_path] = pdir / rel
        return sorted(chosen.items())

    def license_files(self) -> list:
        out = []
        for pattern in self.project.get("license-files", []):
            found = [p for p in walk_files(self.root) if glob_to_regex(pattern).match(p)]
            if not found:
                raise KilnError(f"[project] license-files: {pattern!r} matches no file")
            out += found
        return sorted(set(out))

    # Metadata ---------------------------------------------------------

    def metadata(self) -> str:
        p = self.project
        lines = ["Metadata-Version: 2.4", f"Name: {self.name}", f"Version: {self.version}"]
        if "description" in p:
            lines.append(f"Summary: {p['description']}")
        for person in p.get("authors", []):
            if "email" in person:
                lines.append(f"Author-email: {person.get('name', '')} <{person['email']}>".replace(":  <", ": <"))
            else:
                lines.append(f"Author: {person['name']}")
        if "license" in p:
            if not isinstance(p["license"], str):
                raise KilnError("[project] license must be an SPDX expression string")
            lines.append(f"License-Expression: {p['license']}")
        for f in self.license_files():
            lines.append(f"License-File: {f}")
        if p.get("keywords"):
            lines.append(f"Keywords: {','.join(p['keywords'])}")
        for c in p.get("classifiers", []):
            lines.append(f"Classifier: {c}")
        for label, url in p.get("urls", {}).items():
            lines.append(f"Project-URL: {label}, {url}")
        if "requires-python" in p:
            lines.append(f"Requires-Python: {p['requires-python']}")
        for req in p.get("dependencies", []):
            lines.append(f"Requires-Dist: {req}")
        for extra, reqs in sorted(p.get("optional-dependencies", {}).items()):
            if not EXTRA_RE.match(extra):
                raise KilnError(f"[project.optional-dependencies] invalid extra name {extra!r}")
            lines.append(f"Provides-Extra: {extra}")
            for req in reqs:
                marker = f'extra == "{extra}"'
                if ";" in req:
                    base, _, cond = req.partition(";")
                    lines.append(f"Requires-Dist: {base.strip()}; ({cond.strip()}) and {marker}")
                else:
                    lines.append(f"Requires-Dist: {req.strip()}; {marker}")
        body = ""
        readme = p.get("readme")
        if readme:
            if not isinstance(readme, str):
                raise KilnError("[project] readme must be a file name")
            try:
                body = (self.root / readme).read_text(encoding="utf-8")
            except FileNotFoundError:
                raise KilnError(f"[project] readme: {readme} not found") from None
            ctype = "text/markdown" if readme.endswith(".md") else "text/plain"
            lines.append(f"Description-Content-Type: {ctype}")
        return "\n".join(lines) + "\n\n" + body

    def entry_points(self) -> str:
        groups = {}
        if self.project.get("scripts"):
            groups["console_scripts"] = self.project["scripts"]
        if self.project.get("gui-scripts"):
            groups["gui_scripts"] = self.project["gui-scripts"]
        for group, eps in self.project.get("entry-points", {}).items():
            if group in ("console_scripts", "gui_scripts"):
                raise KilnError(f"[project.entry-points.{group}]: use [project.scripts] or [project.gui-scripts]")
            groups[group] = eps
        out = []
        for group in sorted(groups):
            out.append(f"[{group}]")
            for name, ref in sorted(groups[group].items()):
                if not EP_RE.match(ref.replace(" ", "")):
                    raise KilnError(f"entry point {group}.{name}: invalid reference {ref!r}")
                out.append(f"{name} = {ref}")
            out.append("")
        return "\n".join(out)


# Archives ----------------------------------------------------------------


def _epoch() -> int:
    raw = os.environ.get("SOURCE_DATE_EPOCH")
    return max(int(raw), 315532800) if raw else 315532800


def _zip_info(path: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(path, date_time=time.gmtime(_epoch())[:6])
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    return info


def _record_line(path: str, data: bytes) -> str:
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
    return f"{path},sha256={digest},{len(data)}"


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    project = Project(Path.cwd())
    tag = "py3-none-any"
    filename = f"{project.dist_name}-{project.version}-{tag}.whl"
    dist_info = f"{project.dist_name}-{project.version}.dist-info"
    entries = []
    for wheel_path, src in project.wheel_files():
        entries.append((wheel_path, src.read_bytes()))
    for lic in project.license_files():
        entries.append((f"{dist_info}/licenses/{lic}", (project.root / lic).read_bytes()))
    entries.append((f"{dist_info}/METADATA", project.metadata().encode("utf-8")))
    entries.append((f"{dist_info}/WHEEL", f"Wheel-Version: 1.0\nGenerator: kiln\nRoot-Is-Purelib: true\nTag: {tag}\n".encode()))
    eps = project.entry_points()
    if eps:
        entries.append((f"{dist_info}/entry_points.txt", eps.encode("utf-8")))
    record = [_record_line(p, d) for p, d in entries] + [f"{dist_info}/RECORD,,"]
    entries.append((f"{dist_info}/RECORD", ("\n".join(record) + "\n").encode()))
    os.makedirs(wheel_directory, exist_ok=True)
    with zipfile.ZipFile(os.path.join(wheel_directory, filename), "w") as zf:
        for path, data in entries:
            zf.writestr(_zip_info(path), data)
    return filename


def build_sdist(sdist_directory, config_settings=None):
    """The sdist holds pyproject.toml, the readme, the license files, every
    file the wheel takes from the source directory, and the files matched by
    [tool.kiln] sdist-include (globs relative to the project root)."""
    project = Project(Path.cwd())
    root = project.root
    base = f"{project.dist_name}-{project.version}"
    files = {"pyproject.toml"}
    if project.project.get("readme"):
        files.add(project.project["readme"])
    files.update(project.license_files())
    for _wheel_path, src in project.wheel_files():
        files.add(src.relative_to(root).as_posix())
    include = project.tool.get("sdist-include", [])
    for rel in walk_files(root):
        if matches(rel, include):
            files.add(rel)
    pkg_info = project.metadata().encode("utf-8")
    filename = f"{base}.tar.gz"
    os.makedirs(sdist_directory, exist_ok=True)
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as tf:
        for rel, data in [("PKG-INFO", pkg_info)] + [(f, (root / f).read_bytes()) for f in sorted(files)]:
            info = tarfile.TarInfo(f"{base}/{rel}")
            info.size = len(data)
            info.mtime = _epoch()
            info.mode = 0o644
            info.uname = info.gname = ""
            tf.addfile(info, io.BytesIO(data))
    import gzip

    with open(os.path.join(sdist_directory, filename), "wb") as fh:
        with gzip.GzipFile(filename="", mode="wb", fileobj=fh, mtime=_epoch()) as gz:
            gz.write(raw.getvalue())
    return filename


def get_requires_for_build_wheel(config_settings=None):
    return []


def get_requires_for_build_sdist(config_settings=None):
    return []
