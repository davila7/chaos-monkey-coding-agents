# policy.ini

`data/policy.ini` sets when each stream is rotated, how its archives are
named and compressed, and how long they are kept.

## 1. Format

An INI file. Lines that start with `#` or `;` are comments. It has at most
one `[defaults]` section and one `[stream NAME]` section per stream (one
space between `stream` and the name, which follows `data.md`, section 3).
Each line in a section is `key = value`.

Each setting of a stream comes from its own section, else from
`[defaults]`, else from the built-in value in section 2. A stream with no
section of its own uses `[defaults]` and the built-in values. When
`policy.ini` is missing, every stream uses the built-in values.

## 2. Settings

| Key | Value | Built-in |
|---|---|---|
| `max_size` | a size (section 3) or `off` | `off` |
| `max_age` | a duration (section 3) or `off` | `off` |
| `naming` | `numbered` or `dated` (`rotate.md`, section 2) | `numbered` |
| `offset` | `+HH:MM` or `-HH:MM`, the UTC offset of the day in dated names | `+00:00` |
| `compress_after` | a whole number, 0 or more | `1` |
| `keep` | a whole number, 1 or more | `5` |
| `keep_days` | a whole number, 1 or more, or `off` | `off` |

`max_size` and `max_age` are the thresholds of `rotate.md`, section 3.
`compress_after` is how many of the newest archives stay uncompressed.
`keep` is the most archives a stream keeps; `keep_days` removes archives
older than that many days (`rotate.md`, section 5). `off` turns a setting
off.

## 3. Sizes and durations

A size is a whole number of bytes, optionally followed by `K`, `M` or `G`
in either case, with no space.
`K`, `M` and `G` are 1024, 1024 × 1024 and 1024 × 1024 × 1024 bytes.
So `64K` is 65536 bytes and `2m` is 2097152 bytes.

A duration is a whole number followed by `m` (minutes), `h` (hours) or `d`
(days of 24 hours), lower case, with no space: `90m`, `12h`, `7d`.

## 4. Errors

An unknown section or key, a key given twice in one section, a section
given twice, or a value that breaks section 2 or 3 makes `policy.ini`
invalid. Values are exact: `OFF`, `7 d` or `10KB` are invalid. An invalid
`policy.ini` fails every `rotate` command with the code `policy`, whatever
streams it names.
