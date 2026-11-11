# Types

This note covers the schema and how expanded text becomes a typed value.

## 1. Types

1.1 Every key has one of six types: `string`, `bool`, `int`, `duration`,
`size` and `list`. The schema decides which (section 2).

## 2. The schema

2.1 `DATA/schema.json` is a JSON object with a `types` object that maps
patterns to type names. Other top-level keys are ignored.

2.2 A pattern is one of:

| Pattern | Matches |
|---|---|
| `section.key` | that key of that section; the section is everything before the last dot |
| `section.*` | every key of that section |
| `*.key` | that key in every section |

Section names in patterns are written in lowercase. A section pattern covers
that section only: `server.*` does not cover `server.tls`.

2.3 The type of a key is found in this order: the `section.key` pattern, then
the `section.*` pattern, then the `*.key` pattern. A key that no pattern
matches is a `string`.

2.4 A schema that is not a JSON object with a `types` object, a pattern of
another form, or an unknown type name is a `SchemaError`. It stops the run
(`overview.md` 4.4).

## 3. Conversion

3.1 Conversion reads the expanded text of a value (`interp.md` 4.5). For
every type but `string`, spaces and tabs around the text are removed first.

3.2 Text that does not read as its type is a `ConversionError`.

## 4. string

4.1 The text, as it is.

## 5. bool

5.1 Not case-sensitive:

| Text | Value |
|---|---|
| `true`, `yes`, `on`, `1` | true |
| `false`, `no`, `off`, `0` | false |

Any other text is a `ConversionError`.

## 6. int

6.1 A decimal integer: an optional `+` or `-`, then `0` or a digit from 1 to
9 followed by more digits. A number with a leading zero, such as `007` or
`08080`, is a `ConversionError`.

6.2 A hexadecimal integer: an optional `+` or `-`, then `0x` (lowercase) and
one or more hexadecimal digits in either case.

6.3 In both forms a single `_` may stand between two digits: `1_000_000`,
`0xff_ff`. A `_` at the start or end of the digits, or two in a row, is a
`ConversionError`. So is anything else: spaces inside the number, a decimal
point, an exponent.

## 7. duration

7.1 A duration is one or more parts written together without spaces. Each
part is one or more digits followed by a unit:

| Unit | Means | Milliseconds |
|---|---|---|
| `d` | days | 86400000 |
| `h` | hours | 3600000 |
| `m` | minutes | 60000 |
| `s` | seconds | 1000 |
| `ms` | milliseconds | 1 |

7.2 Each unit appears at most once, and the units appear in the order of the
table, largest first: `1h30m` and `1s500ms` are durations, `30s1m` and `5m5m`
are not.

7.3 The value is the total in milliseconds, as an integer: `1m30s` is 90000,
`250ms` is 250, `2h` is 7200000.

7.4 A number without a unit, a fraction, a sign or a unit not in the table is
a `ConversionError`.

## 8. size

8.1 A size is an amount, optionally followed by a unit, with at most one space
between them. The amount is one or more digits, optionally followed by a `.`
and one or more digits. Units are case-sensitive:

| Unit | Bytes |
|---|---|
| `B` | 1 |
| `KB` | 1000 |
| `MB` | 1000^2 = 1000000 |
| `GB` | 1000^3 = 1000000000 |
| `TB` | 1000^4 |
| `KiB` | 1024 |
| `MiB` | 1024^2 = 1048576 |
| `GiB` | 1024^3 = 1073741824 |
| `TiB` | 1024^4 |

8.2 A size without a unit is in bytes.

8.3 The value is the amount times the unit, as an integer number of bytes. It
must be whole: `1.5KB` is 1500, `1.5KiB` is 1536, `0.5GiB` is 536870912, but
`0.3KiB` (307.2 bytes) and `1.5` are `ConversionError`s.

8.4 Any other text, including a lowercase unit such as `kb` or `kib`, is a
`ConversionError`.

## 9. list

9.1 A list is split at each comma. Spaces and tabs around each item are
removed, and items that are then empty are dropped: `a, b,, c ,` is the list
of `a`, `b` and `c`. An empty text is the empty list.

9.2 Items are strings.
