# The election definition

`election.json` is one JSON object:

    {
      "election": "General municipal election, 2 November 2027",
      "contests": [
        {
          "id": "mayor",
          "title": "Mayor",
          "max_ranks": 6,
          "candidates": [
            {"id": "MA03", "name": "Ana Rocha", "status": "active"},
            {"id": "MA11", "name": "Hugo Vidal", "status": "withdrawn"}
          ],
          "write_ins": [
            {"id": "MA51", "name": "Lúcia Falcão Magalhães",
             "aliases": ["L. F. Magalhães", "Magalhães, Lúcia Falcão", "Lúcia Magalhães"]}
          ],
          "lot_order": ["MA51", "MA11", "MA03"]
        }
      ]
    }

## 1. Contests

1.1 `contests` lists every contest of the election, in the order the results
are written (`output.md` 1.2). A contest is listed even when no ballot of it
was cast or counted.

1.2 `id` is the contest id that records name (`records.md` 4.1).

1.3 `max_ranks` is the number of ranking columns the ballot prints for the
contest. Rankings past `max_ranks` are not part of the ballot
(`counting.md` 1.1).

## 2. Candidates

2.1 `candidates` lists the candidates printed on the ballot. `id` is unique
within the election. Ids are compared without regard to case and to spaces
around them: ` ma03` and `MA03` name the same candidate.

2.2 `status` is `active` or `withdrawn`. A withdrawn candidate withdrew after
the ballots were printed: the name is on the paper and voters mark it, but the
candidate takes no part in the count (`counting.md` 1.2).

## 3. Write-ins

3.1 `write_ins` lists the qualified write-in candidates: people who filed to
be counted when a voter writes their name in. A qualified write-in takes part
in the count like a printed active candidate, under its `id`.

3.2 A write-in mark (`records.md` 4.4) is a mark for a qualified write-in
when its text, compared as in 3.3, equals the `name` or one of the `aliases`
of that write-in. Any other write-in, including one that writes the name of a
printed candidate, is an unqualified write-in and is not a mark for anyone.

3.3 Write-in text is compared after three changes to both sides: every letter
is turned to lower case (Unicode case folding), every character that is
neither a letter nor a digit is turned into a space, and runs of spaces are
turned into one space, with none at either end. Nothing else is changed: in
particular accents stay, so `Inês` and `Ines` are different texts. For
example `R.M.  delgado` and `R. M. Delgado` compare equal; `Delgado, Rosa` and
`Rosa Delgado` do not, unless both are listed.

## 4. The lot

4.1 `lot_order` lists every candidate and qualified write-in of the contest,
in an order drawn by lot before the election. It is used only to break the
last tie of `counting.md` 3.4.
