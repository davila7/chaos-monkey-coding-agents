# Applying hunks

## 1. Order

1.1 The hunks of a section are applied in patch order. Every hunk is matched
against the lines of the file as they were before the section: positions and
line numbers in this note are those of the original file, never of a file
already changed by earlier hunks.

1.2 Sections are independent of each other: each changes its own file
(`paths.md` 2.3).

## 2. Matching

2.1 A hunk matches at a position when its old lines, in order, are equal to
the lines of the file starting at that position (`lines.md` 2). A hunk with
no old line matches at every position, from before the first line to after
the last.

2.2 A hunk whose last old line is marked as having no ending matches only
where that line is the last line of the file and has no ending
(`lines.md` 2.1).

## 3. Where a hunk applies

3.1 **Stated line.** The stated line of a hunk is the start `A` of its old
range (`patch.md` 4). The expected position is line `A`, or right after line
`A` when the old range is empty (`patch.md` 4.2).

3.2 **Carried offset.** The offset of a hunk is the line where it applied
minus its stated line (3.6). Every hunk after the first is expected at its
stated line plus the offset of the last hunk of the same section that
applied. The first hunk, and every hunk before which no hunk applied, has a
carried offset of 0. A rejected hunk carries nothing: the hunk after it uses
the offset of the last hunk that applied.

3.3 **Candidates.** A hunk is tried at every position from its expected
position outwards: the expected position first, then the positions one line
before and one line after, then two lines before and two lines after, and so
on. Of two positions at the same distance, the one before (the lower line
number) is tried first. Positions where the old lines would run past the end
of the file are not tried, and a hunk never applies before the end of the
lines matched by the hunk before it that applied: hunks do not overlap and
keep their order.

3.4 **Fuzz.** When a hunk matches at no candidate position, it is tried again
with fuzz. At fuzz level `f`, up to `f` context lines are dropped from the
start of the hunk and up to `f` from its end; only context lines that come
before the first `-` or `+` line, or after the last one, can be dropped.
Levels are tried in turn, from 0 to the `fuzz` option, and at each level
every candidate position is tried, in the order of 3.3, before any position
at the next level. A match at a lower level always wins over a match at a
higher level, however much nearer the higher-level match is to the expected
position. When the lines are dropped from the start, the expected position
moves down by that many lines. A level that would leave a hunk with old lines
with none is skipped.

3.5 The first match in this order is where the hunk applies. A hunk that
matches nowhere at any level up to the `fuzz` option is rejected; the lines it
would have matched stay as they are, and the other hunks still apply.

3.6 **Reported line.** The line of an applied hunk is the line number of the
first old line it matched, after fuzz dropped lines from its start; for a
hunk with no old line, it is the line after which its lines went (0 at the
start of the file). The stated line used for the offset is `A`, plus the
number of lines fuzz dropped from the start. A hunk that applied where its
header says has offset 0, whatever the offsets of the hunks before it.

## 4. The new lines

4.1 An applied hunk replaces the lines it matched with its new lines: its
context lines, as they are in the file (`lines.md` 3.2), and its added lines,
in hunk order. Context lines dropped by fuzz are not part of the match and
stay as they are.

4.2 Endings follow `lines.md` section 3.
