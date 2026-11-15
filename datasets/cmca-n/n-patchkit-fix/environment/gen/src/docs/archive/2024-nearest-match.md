# Search policy: nearest match first (withdrawn)

Status: withdrawn in release 2.0.0. Kept for the record; see `apply.md`
section 3.4 for the rule that applies.

1. A hunk is tried at its expected position first, at fuzz 0, then at fuzz 1,
   and so on up to the `fuzz` option. Only then is the next candidate
   position tried, again at every fuzz level.

2. The nearest position at which the hunk matches at any fuzz level wins,
   because the line numbers in a patch were thought to be more reliable than
   its context lines.

3. Hunks may be matched anywhere in the file, including before the hunk
   before them, so that a patch whose hunks were reordered by hand still
   applies.

4. Offsets are reported from the expected position of each hunk, so that a
   hunk that moved by the same amount as the one before it shows offset 0.
