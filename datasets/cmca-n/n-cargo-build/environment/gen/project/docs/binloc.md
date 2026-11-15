# binloc

`binloc` checks warehouse bin location codes against the site table compiled into the program
and prints labels for new locations.

    binloc check [--format text|json] [FILE|-]
    binloc label SITE AISLE BAY LEVEL
    binloc sites
    binloc --version
    binloc --help

## Location codes

A location code is `SITE-AISLE-BAY-LEVEL-CHECK`, for example `NB2-07-031-C-A`:

- `SITE`: a site of the table, three letters or digits.
- `AISLE`: one or two digits, from 1 to the site's aisle count.
- `BAY`: one to three digits, from 1 to the site's bay count.
- `LEVEL`: one letter from the site's levels.
- `CHECK`: the ISO/IEC 7064 MOD 37-2 check character of `SITE`, `AISLE` (two digits), `BAY`
  (three digits) and `LEVEL` written together, `NB207031C` for the example. It is one of
  `0-9`, `A-Z` and `*`.

Blanks (spaces and tabs) around a code are ignored and letters may be in either case. The
normalized form has capital letters, a two-digit aisle and a three-digit bay.

The pick zone of a location is `Z1` for aisles 1 to `zone_width` of its site, `Z2` for the
next `zone_width` aisles, and so on. The pick sequence numbers the locations of a site along the
pick path, from 1: aisle by aisle; within an aisle bay by bay, from bay 1 up, except that on a
serpentine site the even aisles run from the last bay down; within a bay, level by level in the
order the site lists them.

Errors, in the order they are checked:

| Message | When |
|---|---|
| `malformed location "<code>"` | not five parts (four without the check character) of the shapes above |
| `unknown site "<SITE>"` | the site is not in the table |
| `aisle <n> is outside <SITE> (1-<aisles>)` | |
| `bay <n> is outside <SITE> (1-<bays>)` | |
| `level <L> is not a level of <SITE> (<levels>)` | |
| `missing check character (expected <C>)` | four parts |
| `check character <X> does not match (expected <C>)` | |

`<code>` is the code without the surrounding blanks, quoted and escaped as Rust's `{:?}` writes
a string.

## binloc check

Reads CSV from FILE, or from standard input when FILE is `-` or missing. A UTF-8 byte order
mark is skipped and lines may end in CRLF. Fields are separated by commas; a field may be
quoted with `"`, with `""` for a quote inside; blanks around fields and around quotes are
ignored. Records do not span lines.

The first line is the header and must hold exactly one column named `location`, in any case.
Every later line that is not blank is a row: it is rejected if it does not split into fields,
if it has a different number of fields than the header, or if its location is not valid.

Text output, one line per valid row, in input order, on standard output:

    NB2-07-031-C-A<TAB>NB2<TAB>Z2<TAB>1953

normalized code, site, zone and sequence. Each rejected row is reported on standard error as
`binloc: line <n>: <error>`, where `<n>` counts every line of the input from 1 for the header.

With `--format json` (or `--format=json`) every row, valid or rejected, is one JSON object on
standard output, in input order, and rejected rows are not reported on standard error:

    {"line":2,"location":"NB2-07-031-C-A","site":"NB2","zone":2,"sequence":1953}
    {"line":3,"error":"check character B does not match (expected A)"}

At the end, `binloc: <rows> checked, <rejected> rejected` goes to standard error. The exit
status is 0 when no row was rejected and 1 otherwise.

Builds without the `json` feature reject `--format json` with
`binloc: json output is not available in this build` and exit status 2, before reading input.

## binloc label

Joins its four arguments with `-`, completes the code with its check character and prints the
normalized code and the scan number, separated by a tab:

    $ binloc label nb2 7 31 c
    NB2-07-031-C-A	00019539

The scan number is the pick sequence in seven digits followed by its Luhn check digit. An
invalid location is reported as `binloc: <error>` with exit status 1; a code that already has a
check character is malformed.

## binloc sites

One line per site, in table order: code, aisles, bays, levels, layout (`serpentine` or
`straight`) and zone width, separated by tabs.

## Errors and exit status

Usage errors (no command, an unknown command, option or format, a missing option value, more
than one input, wrong argument counts) print `binloc: <message>` and the usage text on
standard error and exit with status 2. An input that cannot be read, that is not UTF-8, that
has no header row, or whose header has no `location` column, more than one, or does not split,
is reported as `binloc: <message>` with exit status 2.
