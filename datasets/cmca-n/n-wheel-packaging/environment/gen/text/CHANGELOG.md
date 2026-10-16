# Changelog

## 2.4.0 (2026-09-30)

- Station data is split into one file per station, grouped by region.
- More stations, and updated constants for several existing ones.
- New output formats and updated translations.
- Options can be read from a TOML file (`--config`, `TIDECALC_CONFIG`).
- High and low waters are refined to the minute.

## 2.3.1 (2026-05-12)

- Fixed the sign of the nodal phase correction for O1 and Q1.
- `tidecalc stations` sorts by region, then by file order.

## 2.3.0 (2026-02-02)

- Added `--datum msl`.
- Added `tidecalc constituents`.

## 2.2.0 (2025-10-20)

- Added the plugin interface for output formats.
