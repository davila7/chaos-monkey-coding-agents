# Changelog

## 1.4.0 (in preparation)

- New `isodur sum`, and `isodur_from_ms` in the library. Libtool interface 3 (adds a function,
  so the age goes to 1: `3:0:1`).
- The program is now `isodur`; `durfmt` stays installed as a link to it.
- The unit table moved from `/etc` to the package data directory, `DATADIR/isodur/units.tsv`.
- The build is being reworked for VPATH, `DESTDIR` and `--libdir` installs; see
  `docs/BUILDING.md` for the contract this release must meet.

## 1.3.2

- `fmt --style long` no longer prints a trailing space after the last unit.

## 1.3.0

- Italian and Dutch unit words. Interface unchanged (`2:1:0`).

## 1.2.0

- `isodur_units_load` takes the language; `isodur_units_lang` is removed. Libtool interface 2
  (`2:0:0`, SONAME `libisodur.so.2`).

## 1.1.0

- Short form durations (`1h30m`). Interface `1:1:0`.

## 1.0.0

- First release: `durfmt`, `libisodur` interface `1:0:0` (SONAME `libisodur.so.1`).
