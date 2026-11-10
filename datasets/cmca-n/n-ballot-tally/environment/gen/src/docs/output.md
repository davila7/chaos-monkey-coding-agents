# The tally file

## 1. Layout

1.1 The tally file is one JSON object, written as UTF-8:

    {
      "election": "General municipal election, 2 November 2027",
      "contests": [
        {
          "contest": "mayor",
          "ballots": 1234,
          "winner": "MA03",
          "rounds": [
            {"round": 1, "tallies": {"MA03": 512, "MA07": 431, "MA51": 0}, "exhausted": 12, "eliminated": ["MA51"]},
            {"round": 2, "tallies": {"MA03": 515, "MA07": 433}, "exhausted": 286, "eliminated": []}
          ]
        }
      ]
    }

1.2 `election` is copied from `election.json`. `contests` has one entry per
contest of `election.json`, in the same order.

## 2. One contest

2.1 `contest` is the contest id.

2.2 `ballots` is the number of records of the contest in the batches that
count (`records.md` 3), blank records included.

2.3 `winner` is the id of the candidate who won (`counting.md` 2.2 and 2.4),
or `null` when the contest has no winner (`counting.md` 2.5).

2.4 `rounds` lists every round counted, in order.

## 3. One round

3.1 `round` is the round number, from 1.

3.2 `tallies` maps the id of every candidate continuing in the round to its
votes, 0 included. Withdrawn candidates and candidates eliminated in earlier
rounds are not listed. Ids are written as `election.json` writes them. The
order of the keys carries nothing.

3.3 `exhausted` is the number of ballots of the contest that are exhausted in
the round, blank records included. In every round the votes of `tallies` and
`exhausted` add up to `ballots`.

3.4 `eliminated` lists the ids of the candidates eliminated after the round,
sorted as text. It is empty in the last round.

## 4. Checking

From `/app`:

- `python -m unittest discover -s tests -t .` runs the program on a few small
  inputs and compares each result with the reviewed one next to it.
- `python tools/check_tally.py` runs the program on `/app/data` and on a copy
  of it in another directory, compares `/app/out/tally.json` with the
  certified results of the current election and names the first rounds that
  differ. The certified results are stored as salted digests, so the check
  says whether a round is right, never what it should hold.
