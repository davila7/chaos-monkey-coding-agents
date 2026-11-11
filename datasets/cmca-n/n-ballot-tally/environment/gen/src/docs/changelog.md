# Changelog of the counting rules

## 3.0 (2027-05)

- Candidates with 0 votes are eliminated together after the round
  (`counting.md` 3.1). Up to 2.x they were eliminated one per round through
  the tie rules, which added rounds in which no ballot moved.
- Revisions are compared as numbers (`records.md` 3.1). A batch rescanned ten
  times was counted from revision 9 because `"9"` sorts after `"10"` as text.
- JSON Lines exports can write `revision` as a string of digits.

## 2.1 (2026-09)

- Ties for the fewest votes are broken by going back round by round to
  round 1 (`counting.md` 3.3). 2.0 looked at the previous round only and then
  went to the lot.
- The lot eliminates the tied candidate that comes last in `lot_order`
  (`counting.md` 3.4).

## 2.0 (2026-01)

- An overvoted ranking exhausts the ballot when the count reaches it
  (`counting.md` 1.3). Up to 1.x it was passed over like a skipped ranking,
  so the ballot went on to its next ranking.
- One skipped ranking is passed; two in a row end the ballot (`counting.md`
  1.3). A ranking that only repeats an earlier candidate counts as skipped
  (`counting.md` 1.2 c), and a ranking that only marks withdrawn candidates is
  passed over without counting as skipped (`counting.md` 1.2 b).
- A candidate wins with more than half of the active ballots of the round
  (`counting.md` 2.2), not of all ballots of the contest.

## 1.2 (2025-10)

- Write-in text compared with case folded and punctuation read as spaces
  (`election.md` 3.3). Accents are kept.
- Rankings past `max_ranks` are dropped (`counting.md` 1.1). Some scanners
  export more ranking columns than a contest has, and stray marks from the
  next contest's grid land in them.
