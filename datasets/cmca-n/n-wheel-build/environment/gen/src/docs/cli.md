# The orbis-postal command line

    orbis-postal --version
    orbis-postal format FILE [--renderer NAME] [--from COUNTRY] [--abbreviate | --no-abbreviate]
    orbis-postal check FILE
    orbis-postal countries [--region REGION]
    orbis-postal renderers

`python -m orbis.postal` runs the same program.

## Input

`FILE` holds address records: JSON lines (one object per line, blank lines
ignored), or CSV with a header row when the name ends in `.csv`. Fields:

| Field | Meaning |
|---|---|
| `id` | record identifier; defaults to the record's position (1-based) |
| `country` | ISO 3166 alpha-2 code of the destination, any case; required |
| `recipient`, `organisation` | person and company lines |
| `street`, `number` | street name and house number |
| `extra` | apartment, floor, care-of line |
| `postcode`, `city`, `region` | as written by the sender |

Unknown fields are an error. Whitespace inside a value is collapsed to
single spaces. Record ids must be unique.

## format

Formats every record with the format of its destination country
(docs/formats.md) and writes the output of the chosen renderer (default
`text`) to standard output.

- `--from COUNTRY`: the sender's country. Addresses in that country get no
  country line; all others end with the destination country's English name
  in upper case. Without `--from` every address ends with a country line.
- `--abbreviate`, `--no-abbreviate`: abbreviate street names with the
  country's abbreviation table, or never. Without either option the
  country format decides (`abbreviate` key).

A record whose postcode does not match its country, or whose country is
unknown, is skipped with a message on standard error
(`orbis-postal: skipped: ...`); the others are still rendered and the exit
status is 1.

Built-in renderers:

| Name | Output |
|---|---|
| `text` | the lines of each address, blocks separated by one blank line |
| `oneline` | per address: id, a tab, the lines joined by `, ` |
| `json` | one JSON document: `generator` (`orbis-postal <version>`), `origin`, `count`, `addresses` (id, country, lines) |

Plugins add more (docs/plugins.md); orbis-postal ships `sheet` (A4 sheets of
24 labels, SVG) and `envelope` (DL envelopes, SVG).

## check

Prints one line per record, tab-separated: id, country code, status and
postcode. The status is `OK` (followed by the postcode as printed on mail),
`INVALID` or `UNKNOWN-COUNTRY` (followed by the postcode as given), or
`MISSING`. The exit status is 1 when any record is not `OK`.

## countries

Lists the supported countries, one per line: code, region, English name and
local name, tab-separated, sorted by code. `--region` keeps one region; an
unknown region is an error.

## renderers

Lists the renderers (docs/plugins.md, section 2).

## Exit status

| Status | Meaning |
|---|---|
| 0 | success |
| 1 | some records were skipped or failed the check |
| 2 | bad input, unknown renderer or country, a plugin that cannot be loaded |
| 3 | package data is missing or invalid (country index, format, abbreviation table, label template) |

Errors are printed as `orbis-postal: error: <message>`.
