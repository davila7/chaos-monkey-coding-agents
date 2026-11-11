# Cast vote records

## 1. Files

1.1 Every regular file in `cvr/` whose name ends in `.csv` or `.jsonl` is one
batch file. Other files (`manifest.txt` with the checksums of the export, for
example) are not batch files.

1.2 The name of a batch file is a label the scanner chose. It says nothing
about the batch, its revision or its precinct; those are written inside the
file.

1.3 Batch files are UTF-8 text with lines ending in a line feed. Blank lines
carry nothing.

## 2. Formats

### 2.1 CSV

2.1.1 The file starts with comment lines, then a header row, then one row per
record. A comment line starts with `#`. A comment of the form `# name: value`
is a directive; the directives `batch`, `revision` and `status` give the
batch values of 3.1. Other directives (`scanner`, for example) carry nothing
for the count.

2.1.2 Fields are separated by commas and quoted as usual for CSV: a field that
holds a comma, a double quote or a line break is wrapped in double quotes, and
a double quote inside it is doubled.

2.1.3 The header row names the columns. `ballot` holds the ballot id,
`contest` the contest id, and `rank1`, `rank2`, ... the rankings: `rankN`
holds ranking N. Columns can come in any order, a file can have more ranking
columns than a contest has rankings, and other columns (`sheet`, `style`)
carry nothing for the count. Always find a column by its name.

2.1.4 A ranking cell holds the marks of that ranking separated by `|`. An
empty cell holds no mark. A mark is a candidate id, or `WI:` followed by the
text the voter wrote in.

### 2.2 JSON Lines

2.2.1 One JSON object per line. The first line is the batch object with the
keys `batch`, `revision` and `status` (3.1), and possibly others that carry
nothing for the count.

2.2.2 Every other line is one record:

    {"ballot": "P07-00031", "contest": "mayor",
     "marks": [{"rank": 2, "candidate": "MA03"}, {"rank": 1, "write_in": "rosa delgado"}]}

`marks` lists the marks of the record in any order. Each mark has a `rank`
(the ranking it was made in, a whole number from 1) and either a `candidate`
id or a `write_in` text. Several marks can share a rank. A ranking with no
mark in the list holds no mark.

## 3. Batches and revisions

3.1 Each file is one revision of one batch. `batch` is the batch id, a text.
`revision` is a whole number from 1, written as a number or as a string of
digits; revisions are compared as numbers. `status` is `final` or `void`.

3.2 A batch is scanned again when the first scan was incomplete or misread,
and each rescan is exported as a new revision of the same batch. Only the
revision with the highest number counts; every lower revision of the batch
counts nothing, whatever its status.

3.3 When the highest revision of a batch has status `void`, the batch counts
nothing. Test decks and boxes fed through a scanner twice are voided this
way.

3.4 The records of the batches that count are the records of the election.
No ballot appears in two batches that count.

## 4. Records

4.1 A record gives the marks of one ballot in one contest. Its contest id is
one of the ids of `election.json`, written exactly.

4.2 A record with no mark at all is still a record: the voter left the
contest blank. It is one of the ballots of the contest (`output.md` 2.2) and
it is exhausted from round 1.

4.3 A candidate mark names a candidate id (`election.md` 2.1).

4.4 A write-in mark carries the text the voter wrote. `election.md` 3 says
when it is a mark for a qualified write-in.
