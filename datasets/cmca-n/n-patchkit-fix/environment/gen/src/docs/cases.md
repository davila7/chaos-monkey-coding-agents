# Cases

## 1. Case files

1.1 A case file is a JSON object with these fields:

| Field | Value | Required |
|---|---|---|
| `patch` | the patch text, a string (`patch.md`) | yes |
| `files` | an object that maps a path to the full text of that file | yes |
| `options` | an object of options (section 2) | no |

1.2 Any other field is an error.

1.3 A path in `files` is relative: it is split at `/`, and no part may be
empty, `.` or `..`. File texts are strings and are taken exactly as written,
with their line endings (`lines.md`). An empty string is an empty file.

1.4 The case id is the name of the case file without `.json`.

## 2. Options

2.1 The options and their defaults:

| Option | Value | Default |
|---|---|---|
| `strip` | whole number from 0 to 5: leading path components removed from the paths of the patch (`paths.md` 1) | 1 |
| `fuzz` | whole number from 0 to 3: the highest fuzz level tried (`apply.md` 3.4) | 2 |
| `reverse` | `true` or `false`: apply the patch in reverse (`patch.md` 7) | `false` |

2.2 An unknown option is an error. `true` and `false` are not whole numbers,
and `1.0` and `"1"` are not either.

## 3. Errors

3.1 A case file that is missing, is not UTF-8 JSON, or breaks section 1 or 2
raises `CaseError`. No result is written for the case.
