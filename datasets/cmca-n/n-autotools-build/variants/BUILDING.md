# Building isodur

isodur is a C library (`libisodur`) that parses and formats ISO 8601 durations, a command-line
program (`isodur`) built on it, and a pkg-config module (`isodur`) that other projects use to
build against the installed library. The build uses autoconf, automake and libtool. This document
is the build contract: release engineering checks every rule below on a clean checkout before a
release is tagged. `docs/consuming.md` shows the consumer side, `docs/isodur.md` the program.

## 1. Toolchain

- autoconf 2.71, automake 1.16, libtool 2.4.7, GNU make, gcc 12 (C99) and pkgconf.
- The files that autotools generate (`configure`, `aclocal.m4`, every `Makefile.in`,
  `config.h.in`, `build-aux/` and the libtool macros under `m4/`) are not part of the source
  tree. `autoreconf -fi` in a clean checkout creates them.
- Release builds are VPATH builds: `../configure` from an empty build directory next to the
  source tree. Everything in this document holds for VPATH builds and for in-tree builds.

## 2. Source layout

| Path | Contents |
|---|---|
| `VERSION` | The release version, `MAJOR.MINOR.PATCH`, on one line. The only place it is written. |
| `configure.ac` | The configure script source, including the libtool interface version (section 4). |
| `Makefile.am`, `*/Makefile.am` | The automake input of each directory. |
| `include/isodur/isodur.h` | The public API. |
| `include/isodur/version.h.in` | Template of the generated public header `isodur/version.h`. |
| `lib/` | Library sources and the private header `internal.h`. |
| `src/` | The `isodur` program. |
| `data/units.tsv` | The unit words table read by the library for the long style. |
| `tests/` | `unit.c`, the command-line test script `cli.test` and its cases under `tests/cases/`. |
| `isodur.pc.in` | Template of the pkg-config file. |
| `m4/` | Project macros, if any. libtoolize copies its own macros here. |

## 3. Configure options

| Option | Default | Effect |
|---|---|---|
| `--enable-shared`, `--enable-static` | both enabled | libtool's options. With `--disable-shared` only `libisodur.a` is built and installed. |
| `--disable-tool` | tool built | Builds and installs the library, its headers, the data and the pkg-config file, without `isodur`. |
| `--prefix`, `--exec-prefix`, `--libdir`, `--includedir`, `--datarootdir`, `--datadir`, `--bindir` | GNU defaults | Every install path, and every path compiled into a program or written into an installed file, comes from these. |

`make install` and `make uninstall` honour `DESTDIR`: with `DESTDIR` set they write and remove
files only under `DESTDIR`, and nothing they install holds the `DESTDIR` path.

## 4. Version numbers

- `VERSION` holds the release number. `configure.ac` reads it in `AC_INIT`, so `isodur --version`,
  `isodur/version.h` and the `Version` field of `isodur.pc` all follow `VERSION`.
- The libtool interface version of `libisodur` is set in `configure.ac` by three `m4_define`
  lines (`isodur_lt_current`, `isodur_lt_revision`, `isodur_lt_age`) and substituted as
  `ISODUR_LT_VERSION` in the form `CURRENT:REVISION:AGE`.
- `lib/Makefile.am` writes the interface numbers after `-version-info` itself (LTV-3318: they are kept in step with the release by hand).
- The interface version is the release number written as `MAJOR:MINOR:PATCH` (LTV-3318), so it changes with every release.
- For 1.4.0 the interface version is `1:4:0`, the release number.
- On GNU/Linux libtool names the library `libisodur.so.C-A.A.R`, so 1.4.0 installs `libisodur.so.1.0.4` with the SONAME `libisodur.so.1`.

## 5. The library

- The shared library exports exactly the functions declared in `isodur/isodur.h`: the symbols
  that start with `isodur_` followed by a letter. The internal helpers, named `isodur__*`, are
  not exported (`-export-symbols-regex`).
- The library calls `lround` from the C math library. `configure` finds the math library with
  `LT_LIB_M`, and `libisodur` links it itself, so a program that links `libisodur` needs no
  `-lm` of its own. For static links the pkg-config file names it (section 8).

## 6. The program

- `isodur` reads `units.tsv` from the directory compiled into it, which is the package data
  directory as `make` expands it: `$(pkgdatadir)`, that is `DATADIR/isodur` for the configured
  `DATADIR`. `--data DIR` overrides it at run time; the tests use that.
- The program is also installed as `durfmt`, the 1.x name, which runs `isodur fmt`. `durfmt` is
  a relative symbolic link to `isodur` in the same directory, made by `make install` and removed
  by `make uninstall`.

## 7. Installed layout

`LIBDIR` stands for the configured `--libdir`, `DATADIR` for `--datadir`, and so on.

| Path | Notes |
|---|---|
| `BINDIR/isodur` | not with `--disable-tool` |
| `BINDIR/durfmt` | symbolic link to `isodur`; not with `--disable-tool` |
| `INCLUDEDIR/isodur/isodur.h` | |
| `INCLUDEDIR/isodur/version.h` | generated |
| `LIBDIR/libisodur.so.1.0.4`, `LIBDIR/libisodur.so.1`, `LIBDIR/libisodur.so` | shared builds; the last two are symbolic links |
| `LIBDIR/libisodur.a` | static builds |
| `LIBDIR/libisodur.la` | |
| `LIBDIR/pkgconfig/isodur.pc` | |
| `DATADIR/isodur/units.tsv` | |

Consumers include `<isodur/isodur.h>`, which includes `<isodur/version.h>`.

## 8. The pkg-config file

- `isodur.pc` is generated by `configure` from `isodur.pc.in` and installed into
  `LIBDIR/pkgconfig`.
- It defines `prefix`, `exec_prefix`, `libdir`, `includedir`, `datarootdir`, `datadir` and
  `pkgdatadir` (`DATADIR/isodur`, where consumers find `units.tsv`), each from the configured
  value; no path is written into the template.
- `Libs` is `-L${libdir} -lisodur`. `Libs.private` names the math library found by `configure`,
  so that `pkg-config --static --libs isodur` links a static `libisodur`. `Cflags` is
  `-I${includedir}`.

## 9. Tests

- `make check` runs `unit` and, when the program is built, `cli.test`.
- `cli.test` takes the program, the data directory and the cases directory from the environment
  variables `ISODUR`, `DATA` and `CASES`, which `tests/Makefile.am` sets through
  `AM_TESTS_ENVIRONMENT`. The script is run with `$(SHELL)`.
- `make check` passes in VPATH builds, in-tree builds and builds from the release tarball.

## 10. Distribution

- `make distcheck` passes.
- The tarball (`make dist`) holds everything needed to build, test and regenerate the package:
  every source and header including `lib/internal.h`, `data/units.tsv`, `tests/cli.test` with
  every case, the docs, `CHANGELOG.md`, `VERSION` and the autotools inputs. `autoreconf -fi`
  followed by `configure` and `make` works in an unpacked tarball.
