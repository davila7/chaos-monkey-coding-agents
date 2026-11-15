# Patch text

## 1. Lines of a patch

1.1 The patch text is split into lines at each line feed. A final line feed
ends the last line and does not start another one.

1.2 A carriage return right before the line feed belongs to the line ending,
not to the line. A patch made from files with CRLF endings carries a carriage
return at the end of each hunk line (`+`, `-` and space lines); once it is
removed, those lines compare equal to the same lines of a file with LF
endings, or with CRLF endings (`lines.md` 2). A carriage return anywhere else
is part of the line.

## 2. File sections

2.1 A file section starts with a line that begins with `--- ` (three minus
signs and a space) directly followed by a line that begins with `+++ `. The
first names the old file, the second the new file. The hunks of the section
follow directly (section 3).

2.2 The path of a `---` or `+++` line is the text after the four leading
characters, up to the first tab or the end of the line. Text after the tab,
usually a date, is ignored. Spaces belong to the path:
`--- a/my notes.txt<TAB>2026-01-02 10:00:00` names `a/my notes.txt`. An empty
path is an error.

2.3 The path `/dev/null` on the `---` line means the section creates its file;
on the `+++` line it means the section deletes it (`paths.md` 3). Both paths
`/dev/null` is an error.

2.4 Lines outside sections and hunks are ignored: mail headers, `diff --git`,
`index`, `new file mode`, `Only in`, free text. A `---` line that is not
directly followed by a `+++` line is such a line.

2.5 A section with no hunk is an error. A patch with no section is an error.
A hunk header outside a section is an error.

## 3. Hunk headers

3.1 A hunk starts with a header line:

    @@ -A,B +C,D @@ optional text

`A` and `B` give the old range, `C` and `D` the new range. The text after the
second `@@` and a space, often the name of a function, is ignored.

3.2 A range without a count, `-A` or `+C`, has a count of 1. `@@ -7 +7,2 @@`
has an old range of one line, line 7.

3.3 A header that does not have this form is an error.

## 4. Ranges

4.1 A range with a count of 1 or more starts at line `A` (or `C`), counting
from 1, and covers `B` (or `D`) lines. Its start cannot be 0.

4.2 A range with a count of 0 covers no line. Its start is the line after
which the hunk's lines go: `@@ -5,0 +6,2 @@` adds two lines after old line 5,
and `@@ -0,0 +1,3 @@` adds three lines at the start of the file. In the
terms of `apply.md`, the expected position of such a hunk is right after line
`A`, not at line `A`.

## 5. Hunk lines

5.1 After the header come exactly as many old lines as the old count and as
many new lines as the new count. A line that starts with a space is a context
line: it is both an old and a new line. A line that starts with `-` is an old
line only (removed), a line that starts with `+` a new line only (added).
The text of a hunk line is what follows its first character.

5.2 A completely empty line inside a hunk counts as a context line whose text
is empty: some mail programs drop the single space of an empty context line.

5.3 A line that starts with a backslash, usually
`\ No newline at end of file`, is an end-of-file marker. It is not a hunk
line and is not counted. It says that the hunk line just before it is the
last line of its file and has no line ending. After a `-` line it speaks of
the old file, after a `+` line of the new file, and after a context line of
both. A marker may directly follow the last line of a hunk.

5.4 A marked line must be the last old line of its hunk (for the old file) or
the last new line (for the new file). Anything else is an error, and so is a
marker before the first hunk line.

5.5 A hunk that ends before its counts are reached, a line inside the counts
that does not start with a space, `-`, `+` or a backslash, and more lines of
one kind than the header gives are errors.

## 6. Errors

6.1 Patch text that breaks this note raises `PatchSyntaxError`. No result is
written for the case.

## 7. Reverse patches

7.1 With the `reverse` option, each section is replaced by the section that
undoes it, before anything else uses it: the `---` and `+++` paths swap, the
old and new ranges of each header swap, `-` lines become `+` lines and `+`
lines become `-` lines, and context lines stay.

7.2 End-of-file markers swap sides with their lines. A marker that spoke of
the new file speaks of the old file of the reversed section, and the other
way round. A patch that changed a last line without a newline into one with a
newline, reversed, matches a file whose last line has a newline and leaves
the old last line without one.

7.3 A reversed creation is a deletion and a reversed deletion is a creation
(`paths.md` 3).
