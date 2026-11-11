# Configuration policy: size units (withdrawn)

Status: withdrawn in release 3.0.0. Kept for the record; see `types.md`
section 8 for the rule that applies.

1. Every size unit is a power of 1024: `KB` and `KiB` are both 1024 bytes,
   `MB` and `MiB` are both 1048576 bytes, and so on up to `TB`.

2. Sizes are written in whole units only; `1.5KB` is not a size.

3. Rationale: memory limits and buffer sizes were configured in binary
   multiples, and operators wrote `KB` and `MB` for them.
