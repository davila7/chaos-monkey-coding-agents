"""The build defects of the shipped tree, as edits to the correct tree in project/.

apply(root, ids) applies the listed text edits, in the order of BUGS, to a copy of the
correct tree. Each edit replaces text that must occur exactly once. "msrv-dep" has no text
edit: build.py writes Cargo.lock and vendor/ for it (MSRV_DEP).
"""

from __future__ import annotations

from pathlib import Path

ROOT = "Cargo.toml"
CORE = "crates/binloc-core/Cargo.toml"
CLI = "crates/binloc/Cargo.toml"
MAKE = "Makefile"

# The fieldsplit release in the shipped Cargo.lock and vendor/; 0.4.1 is the newest one that
# rustc 1.63 builds.
MSRV_DEP = ("fieldsplit", "0.4.3")

BUGS: dict[str, list[tuple[str, str, str]]] = {
    # The workspace claims a newer compiler than the builders have.
    "rust-version": [
        (ROOT, 'rust-version = "1.63"\n', 'rust-version = "1.65"\n'),
    ],
    # let-else is stable from Rust 1.65.
    "let-else": [
        ("crates/binloc-core/src/lib.rs",
         "    let site = match find_site(parts[0]) {\n"
         "        Some(site) => site,\n"
         "        None => return Err(LocError::UnknownSite(parts[0].to_ascii_uppercase())),\n"
         "    };\n",
         "    let Some(site) = find_site(parts[0]) else {\n"
         "        return Err(LocError::UnknownSite(parts[0].to_ascii_uppercase()));\n"
         "    };\n"),
    ],
    # Cargo.lock and vendor/ hold a release that needs rustc 1.70.
    "msrv-dep": [],
    # The core crate relies on the feature the binary enables; it fails when built on its own.
    "feature": [
        (CORE, 'checkchar = { version = "1.2", default-features = false, features = ["iso7064"] }\n',
         'checkchar = { version = "1.2", default-features = false }\n'),
    ],
    # The json writer is compiled even without the json feature.
    "cfg-json": [
        ("crates/binloc/src/main.rs", '#[cfg(feature = "json")]\nfn emit_json(', "fn emit_json("),
        ("crates/binloc/src/main.rs",
         '#[cfg(not(feature = "json"))]\n'
         "fn emit_json(_row: &Row, _out: &mut dyn Write) -> io::Result<()> {\n"
         '    unreachable!("json output is not built in")\n'
         "}\n\n",
         ""),
    ],
    # An edit to the site table does not rerun the build script.
    "rerun": [
        ("crates/binloc-core/build.rs", '    println!("cargo:rerun-if-changed={}", TABLE);\n', ""),
    ],
    # Without the path mapping the binary records the checkout directory.
    "remap": [
        (MAKE, "export RUSTFLAGS := --remap-path-prefix=$(CURDIR)=/build/binloc\n", ""),
    ],
    # Only the listed test target runs; tests/formats.rs is skipped.
    "autotests": [
        (CLI, 'description = "Checks and labels warehouse bin locations"\n',
         'description = "Checks and labels warehouse bin locations"\nautotests = false\n'),
        (CLI, 'fieldsplit = "0.4"\n', 'fieldsplit = "0.4"\n\n[[test]]\nname = "cli"\npath = "tests/cli.rs"\n'),
    ],
    # The binary keeps the version of the previous release instead of the workspace version.
    "pkg-version": [
        (CLI, 'name = "binloc"\nversion.workspace = true\n', 'name = "binloc"\nversion = "2.2.0"\n'),
    ],
}

ALL = list(BUGS)


def apply(root: Path, ids: list[str]) -> None:
    unknown = set(ids) - set(BUGS)
    if unknown:
        raise SystemExit(f"unknown defects: {sorted(unknown)}")
    for bug in BUGS:
        if bug not in ids:
            continue
        for path, old, new in BUGS[bug]:
            p = root / path
            text = p.read_text()
            n = text.count(old)
            if n != 1:
                raise SystemExit(f"{bug}: {path}: expected text found {n} times")
            p.write_text(text.replace(old, new))
