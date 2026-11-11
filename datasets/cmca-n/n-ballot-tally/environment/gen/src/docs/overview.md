# Ranked-choice tally: overview

The city elects its mayor, council members, school board and district
commissions by ranked-choice voting: a voter ranks candidates in order of
preference, and the count runs in rounds, eliminating the last candidate of
each round, until one candidate holds a majority. The ballot scanners at the
polling places export cast vote records in batches. The tally program reads
the election definition and every batch, and writes the round-by-round
results of every contest. This note says what goes in, what comes out and in
which order the work is done. The rules for each step live in their own
notes:

| Note | Covers |
|---|---|
| `election.md` | the election definition: contests, candidates, write-ins, the lot |
| `records.md` | the cast vote record files, batches and revisions, how marks are written |
| `counting.md` | how a ballot is read, when it counts for whom, the rounds |
| `output.md` | the tally file |
| `changelog.md` | what changed between versions of these rules |

Where this note and a numbered rule in another note seem to disagree, the
numbered rule wins. The rules apply to every election the same way: nothing in
them depends on a particular contest, precinct, batch or candidate.

## 1. Inputs

1.1 An input directory holds `election.json` (`election.md`) and a directory
`cvr/` with the batch files of every scanner (`records.md`).

1.2 The input directory of a real election night holds batches that must not
be counted: rescans that a later revision replaced, a test deck run before the
polls opened, boxes that were scanned twice and voided. `records.md` 3 says
which batches count.

## 2. Steps

1. Read the election definition (`election.md`).
2. Read every batch file and keep the batches that count (`records.md` 3).
3. Read each record of those batches into the rankings of one ballot in one
   contest (`records.md` 4 and `counting.md` 1).
4. For each contest, run the rounds (`counting.md` 2 and 3) until the contest
   has a winner or no ballot is left to count.

Then write the results of every contest to one file (`output.md`).

## 3. Terms

- A **ballot** is one voter's paper. It can hold several contests; each
  contest of a ballot is one **record** in a batch file.
- A **ranking** is the column of one rank (first choice, second choice, and
  so on) of one contest on one ballot. A ranking can hold no mark, one mark,
  or several marks.
- A **candidate** is a person printed on the ballot or a qualified write-in
  (`election.md` 3). A candidate is **continuing** in a round when the
  candidate has not been eliminated in an earlier round. Withdrawn candidates
  are never continuing.
- A ballot is **exhausted** in a round when it counts for no continuing
  candidate in that round (`counting.md` 1.3). A ballot that is exhausted in a
  round is exhausted in every later round.
- The **active ballots** of a round are the ballots of the contest that are
  not exhausted in that round.

## 4. Running the program

4.1 The program reads one input directory and writes one tally file:

    python3 /app/bin/tally.py INPUT_DIR OUTPUT_FILE

It uses only the Python standard library, reads nothing outside `INPUT_DIR`
and writes nothing but `OUTPUT_FILE`. The same input gives the same output
wherever the input directory is, and whatever the order in which the files of
`cvr/` are listed.

4.2 The input is valid: every file named in these notes parses, every
candidate id in a record belongs to the contest of that record, and two files
of one batch never carry the same revision. A program does not have to check
this.

## 5. What the results are used for

The results file is published as it is and is the basis of the certified
count. A round that is missing, an extra round, or one vote in the wrong
place makes the published count wrong.
