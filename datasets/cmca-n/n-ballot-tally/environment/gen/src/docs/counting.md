# Counting

## 1. Reading a ballot

1.1 A ballot has rankings 1 to `max_ranks` of its contest (`election.md`
1.3). Marks in a ranking past `max_ranks` are not part of the ballot and are
dropped before anything else.

1.2 Each ranking, from ranking 1 onward, is read in four steps. Each step
works on the marks the step before it left.

a. **Write-ins.** A write-in mark for a qualified write-in becomes a mark
   for that write-in candidate. An unqualified write-in mark is removed.
   Several marks for one candidate are one mark. A ranking that holds no mark
   now (because it never held one, or because only unqualified write-ins
   were written in it) is **skipped**, and the next steps do not apply to it.
b. **Withdrawn candidates.** Marks for withdrawn candidates are removed. A
   ranking that this step leaves with no mark is **passed over**: it is
   neither skipped nor a choice.
c. **Repeats.** Marks for a candidate that the ballot already marked in an
   earlier ranking (as that ranking was left by step b, overvoted rankings
   included) are removed. A ranking that this step leaves with no mark is
   **skipped**.
d. **What is left.** A mark for one candidate is a **choice** of that
   candidate. Marks for two or more different candidates make the ranking
   **overvoted**.

1.3 In each round a ballot is read from ranking 1 onward, and the first
ranking below that decides is the one that counts:

- A choice of a continuing candidate: the ballot counts for that candidate.
- A choice of a candidate eliminated in an earlier round: go on to the next
  ranking.
- A ranking that is passed over: go on to the next ranking.
- An overvoted ranking: the ballot is exhausted, whatever candidates the marks are for, eliminated or not.
- A skipped ranking: when the next ranking is skipped too, the ballot is
  exhausted. Otherwise go on to the next ranking. One skipped ranking is
  passed; two skipped rankings in a row end the ballot.
- No ranking left: the ballot is exhausted.

1.4 Examples, for a contest with `max_ranks` 5 and continuing candidates A, B
and C (a dash is an empty ranking):

| Rankings | Counts for |
|---|---|
| `- A B - -` | A |
| `- - A B C` | exhausted |
| `A\|B C - - -` | exhausted, even when A is eliminated |
| `D A - - -` with D eliminated | A |
| `W - B - -` with W withdrawn | B |
| `X B - - -` with X an unqualified write-in | B |
| `B B - - C` with B eliminated | exhausted (ranking 2 is a repeat, so rankings 2 and 3 are both skipped) |

## 2. Rounds

2.1 In round 1 every candidate of the contest is continuing: the printed
candidates with status `active` and the qualified write-ins. Every ballot of
the contest is read as in 1.3, and each active ballot adds one vote to the
candidate it counts for.

2.2 A candidate wins in a round when the candidate's votes are more than half
of the active ballots of that round. Exhausted ballots are not part of that
count. When a candidate wins, the count of the contest stops.

2.3 Otherwise candidates are eliminated as in section 3, and the next round
is counted with the candidates that are still continuing. Every ballot is
read again from ranking 1 in every round.

2.4 When a round starts with one continuing candidate, that candidate wins in
that round.

2.5 When round 1 has no active ballot (the contest has no records, or every
record is exhausted), round 1 is still recorded, with every candidate at 0
votes, and the contest has no winner.

## 3. Elimination

3.1 When one or more continuing candidates have 0 votes in a round, all of
them are eliminated together after that round, and nobody else.

3.2 Otherwise the one candidate with the fewest votes in the round is
eliminated.

3.3 When several candidates share the fewest votes, the tie is broken by the
rounds before: of the tied candidates, keep those with the fewest votes in the
previous round; if more than one is left, do the same with the round before
that, and so on back to round 1. Example: B and C have 33 votes each in
round 3; they had 30 each in round 2, and B had 30 and C 28 in round 1, so C
is eliminated.

3.4 When candidates are still tied after round 1, or tie in round 1 itself,
the one that comes last in `lot_order` (`election.md` 4) is eliminated.
