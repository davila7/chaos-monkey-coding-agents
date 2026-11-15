# Output

## 1. Errors

1.1 A case that cannot be applied gets no result. Its error is reported as
`<Class>: <message>`, where the class is one of `CaseError`,
`PatchSyntaxError` and `PathError` (`cases.md` 3, `patch.md` 6, `paths.md` 4).

1.2 `run` writes `OUT/errors.json`: a list of `{"case": ID, "error": TEXT}`
objects, one per case that could not be applied, in ascending order of case
id. An empty run writes `[]`.

## 2. Results

2.1 A result is an object with these fields, in this order:

| Field | Value |
|---|---|
| `case` | the case id |
| `options` | `{"strip": S, "fuzz": F, "reverse": R}`, the options in force, defaults included |
| `files` | one entry per section (2.2) |
| `untouched` | the paths of the case that no section names, in ascending order of code points |

2.2 `files` has one entry per section, in patch order: the order in which the
sections appear in the patch text, which is not the order of their paths. An
entry is an object with these fields, in this order:

| Field | Value |
|---|---|
| `path` | the file the section changes (`paths.md` 2) |
| `action` | `modify`, `create` or `delete` |
| `status` | 2.3 |
| `hunks` | one report per hunk of the section, in hunk order (2.4) |
| `content` | the full text of the file after the section, or `null` (2.5) |

2.3 `status` is `applied` when every hunk applied, `rejected` when none did,
and `partial` otherwise. A deletion whose hunks all applied but left lines is
`partial` (`paths.md` 3.2).

2.4 A hunk report is `{"hunk": N, "result": R, "line": L, "offset": O,
"fuzz": F}`. `N` is the number of the hunk in its section, from 1. `R` is
`applied` or `rejected`. For an applied hunk, `L` is its reported line, `O`
its offset (`apply.md` 3.6) and `F` the fuzz level at which it matched. For a
rejected hunk, `L`, `O` and `F` are `null`.

2.5 `content` is `null` for a file that was deleted, and for a file to be
created whose every hunk was rejected. Otherwise it is the whole text of the
file after the section, with every line ending (`lines.md`).

## 3. Summary listing

3.1 `run` writes `OUT/summary.json`: a list with one row per result, in
ascending order of case id. A row is an object with these fields, in this
order:

| Field | Value |
|---|---|
| `case` | the case id |
| `files` | the number of entries in `files` |
| `hunks` | the number of hunk reports |
| `applied` | the number of applied hunks |
| `moved` | the number of applied hunks whose offset is not 0 |
| `fuzzed` | the number of applied hunks whose fuzz is not 0 |
| `rejected` | the number of rejected hunks |

3.2 `moved` and `fuzzed` count independently: a hunk that applied at its
stated line with fuzz 1 is fuzzed but not moved.

## 4. JSON format

4.1 Every file `run` writes is JSON indented by two spaces, with a newline at
the end. Results, entries, reports and rows keep their fields in the order
given above.
