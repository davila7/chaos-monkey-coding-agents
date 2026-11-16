# Paths

## 1. Strip

1.1 Paths in a patch are split at `/`. The `strip` option (`cases.md` 2)
removes that many leading parts. With `strip` 1, `a/src/main.c` becomes
`src/main.c`; with `strip` 0 it stays `a/src/main.c`.

1.2 A path with no more than `strip` parts is an error. After stripping, the
path must be relative as `cases.md` 1.3 says: no empty, `.` or `..` part.
A path that starts with `/` has an empty first part, so with `strip` 0 it is
an error.

1.3 `/dev/null` is never stripped.

## 2. The file of a section

2.1 Paths are worked out after `reverse` (`patch.md` 7).

2.2 When neither path is `/dev/null`, the section modifies a file. Both paths,
stripped, must be the same; the package does not rename files.

2.3 Two sections of one patch that name the same file are an error.

## 3. Created and deleted files

3.1 A section whose old path is `/dev/null` creates the file of its new path.
The case must not have that file. The section's hunks apply to an empty file.

3.2 A section whose new path is `/dev/null` deletes the file of its old path.
The case must have that file. The file is deleted only when every hunk of the
section applied and no line is left; otherwise it stays, with the lines that
are left, and its status is `partial` (`output.md` 2.3).

3.3 A section that modifies a file needs the case to have that file.

## 4. Errors

4.1 A section that breaks this note raises `PathError`. No result is written
for the case.
