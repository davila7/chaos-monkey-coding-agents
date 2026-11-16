# Changelog

## 2.3.0

- `sections` prints the sections of a case as the package reads them
  (`overview.md` 4.3).
- Reverse patches swap the sides of end-of-file markers (`patch.md` 7.2).

## 2.0.0

- Fuzz levels are tried in turn, each over every candidate position, before
  the next level (`apply.md` 3.4). Up to 1.x each position was tried at every
  fuzz level before the next position, so a fuzzy match next to the expected
  line won over an exact match a few lines further down, and hunks landed on
  look-alike blocks. The nearest-match policy behind that order is withdrawn
  (see `archive/2024-nearest-match.md`).
- A hunk never applies before the end of the hunk before it (`apply.md` 3.3).
- Offsets are reported from the stated line of each hunk, not from its
  expected position (`apply.md` 3.6).

## 1.4.0

- Patches made from CRLF files: the carriage return at the end of a patch line
  belongs to the line ending (`patch.md` 1.2).
- Added lines take the ending of the file (`lines.md` 3.1).

## 1.2.0

- Paths end at the first tab, and may hold spaces (`patch.md` 2.2).
- Empty context lines dropped to a bare empty line by mail programs
  (`patch.md` 5.2).
