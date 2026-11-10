# Output

This note covers what `run` writes (`overview.md` 4.4): resolved documents,
the summary listing and the error listing, and the format of every document.

## 1. Files

    OUT/resolved/<id>.json   one resolved document per config that resolved
    OUT/summary.json         the summary listing
    OUT/errors.json          the configs that could not be resolved

## 2. Resolved documents

2.1 A resolved document is a JSON object with these keys, in this order:

| Key | Value |
|---|---|
| `config` | the config id |
| `includes` | the shared files the config read (`include.md` section 4) |
| `settings` | one object per written section, holding its keys and their typed values |

2.2 In `settings`, sections appear in code point order of their names, and
within a section, keys appear in code point order. A section exists in the
document when at least one key was assigned in it; a header alone adds
nothing.

2.3 Template sections, whose names start with `_` (`syntax.md` 3.6), are not
written. Their values are not counted anywhere in the output.

2.4 Values are written as JSON by type (`types.md`): a `string` as a string,
a `bool` as `true` or `false`, an `int`, a `duration` and a `size` as integers,
and a `list` as an array of strings.

    {
      "config": "edge",
      "includes": [
        "tls.conf",
        "base.conf"
      ],
      "settings": {
        "server": {
          "port": 8443,
          "tags": [
            "blue",
            "green"
          ],
          "timeout": 90000
        }
      }
    }

## 3. Summary listing

3.1 `summary.json` is an array with one row per resolved document, sorted by
config id in code point order. Each row has these keys, in this order:

| Key | Value |
|---|---|
| `config` | the config id |
| `sections` | the number of sections in the document's `settings` |
| `keys` | the number of keys in the document's `settings` |
| `includes` | the number of entries in the document's `includes` |

## 4. Error listing

4.1 `errors.json` is an array with one row per config that could not be
resolved, sorted by config id. Each row has the keys `config` and `error`,
where `error` is the name of the error class, a colon, a space and a message.

4.2 The error classes are `ParseError` (`syntax.md`), `IncludeError`
(`include.md`), `InterpolationError` (`interp.md`) and `ConversionError`
(`types.md`). A `SchemaError` stops the run instead (`types.md` 2.4).

## 5. JSON format

5.1 Every document is written as JSON with two-space indentation and the keys
in the order this note lists them, followed by a newline. Characters outside
ASCII are written as `\u` escapes.
