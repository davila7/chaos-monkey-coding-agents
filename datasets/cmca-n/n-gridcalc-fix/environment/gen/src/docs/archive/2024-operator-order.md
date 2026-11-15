# Formula policy: operator order (withdrawn)

Status: withdrawn in release 2.0.0. Kept for the record; see `formulas.md`
section 3 for the rule that applies.

1. A prefix minus or plus binds tighter than every infix operator, `^`
   included: `-2^2` is `(-2)^2`, which is 4.

2. `^` groups to the left like the other arithmetic operators: `2^3^2` is
   `(2^3)^2`, which is 64.

3. Rationale: sheets were exchanged with spreadsheet programs that read
   formulas this way, and the same text was meant to give the same value.
