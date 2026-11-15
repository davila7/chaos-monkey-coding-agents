# Lines and line endings

## 1. Lines of a file

1.1 A file text is split into lines. Each line keeps its line ending: CRLF
(carriage return and line feed), LF, or none. Only the last line of a file can
have no ending; a file whose text does not end with a line feed has such a
last line. An empty text has no line.

1.2 A carriage return that is not directly followed by a line feed is part of
the line.

1.3 Files can mix CRLF and LF lines. Each line keeps its own ending.

## 2. Comparing lines

2.1 A hunk line and a file line are equal when their texts are equal, without
endings. Endings never decide whether a hunk matches, with one exception: an
old line marked as having no line ending (`patch.md` 5.3) matches only the
last line of the file, and only when that line has no ending.

## 3. Endings of the new lines

3.1 Added lines take the ending of the file: the ending of the first line of
the file, before the patch, that has one. A file with no line that has an
ending (an empty file, or a single line without one) uses LF.

3.2 Context lines are not rewritten: each keeps its text and ending from the
file. Lines outside the hunks are not touched. The package never converts the
endings of a file: a CRLF file stays CRLF, and in a file that mixes endings
every untouched line keeps its own.

3.3 A new line marked as having no ending (`patch.md` 5.3) gets none. It is
the last line of the new file.

3.4 After the hunks are applied, every line but the last has an ending: a
line that had none but is no longer last, because lines were added after it,
gets the ending of the file (3.1). The last line keeps what it has.
