# Residents survey tables: overview

The residents survey is fielded online. During fieldwork the form changed
twice, so the response exports come from three form versions that name,
order and code some questions differently. The tables program turns all
exports of a survey into one tables file: a summary of the responses received
and kept, and one weighted crosstab per planned table, which the research
team loads as it is.

This note says what goes in, what comes out and in which order the work is
done. The rules for each step live in their own notes:

| Note | Covers |
|---|---|
| `exports.md` | export files: delimiters, header, cells |
| `codebook.md` | form versions, questions, reading answers, routing |
| `cleaning.md` | duplicates, partial responses, speeders |
| `weighting.md` | raking to the targets, trimming |
| `tables.md` | banner columns, bases, percentages, nets, means |
| `output.md` | the tables file |
| `changelog.md` | what changed between versions of these rules |

Where this note and a numbered rule in another note seem to disagree, the
numbered rule wins. The rules apply to every survey the same way: nothing in
them depends on a particular respondent, file, question or date.

## 1. Inputs

1.1 An input directory holds four things:

- `codebook.json`: the survey, its form versions and its questions
  (`codebook.md`);
- `weighting.json`: the weighting targets and settings (`weighting.md`);
- `tables.json`: the table plan (`tables.md`);
- `exports/`: the response exports (`exports.md`).

1.2 Every export row is one submission of the form by one respondent. A
respondent can submit more than once, under the same or another form
version, and the same submission can be exported twice. The file name of an
export says nothing reliable about what it holds.

## 2. Steps

1. Read every export (`exports.md`) and find the form version of each row
   (`codebook.md` 2).
2. Keep one row per respondent (`cleaning.md` 1).
3. Drop partial responses that ended too early (`cleaning.md` 2), then drop
   speeders (`cleaning.md` 3). What is left are the kept respondents.
4. For each kept respondent, decide which questions they were asked and read
   their answers (`codebook.md` 4 and 5).
5. Weight the kept respondents (`weighting.md`).
6. Build the planned tables (`tables.md`) and write the tables file
   (`output.md`).

## 3. Terms

- A **row** is one line of data in an export.
- A **respondent** is a respondent id. Rows with the same id belong to the
  same respondent.
- A **complete** row is one whose status says the form was finished; every
  other row is **partial** (`codebook.md` 2.3).
- A **valid answer** is what a respondent who was asked a question answered,
  after the reading rules of `codebook.md` 4: a code (single choice, age
  band) or a non-empty set of codes (multiple choice). A respondent who was
  not asked, left the question empty or gave only codes marked `missing` has
  no valid answer.

## 4. Running the program

4.1 The program reads one input directory and writes one tables file:

    python3 /app/bin/crosstabs.py INPUT_DIR OUTPUT_FILE

It uses only the Python standard library, reads nothing outside `INPUT_DIR`
and writes nothing but `OUTPUT_FILE`. The same input gives the same output
wherever the input directory is.

4.2 The inputs are well formed: the JSON files follow their notes, every row
has a form version the codebook defines, every value a recode map is applied
to is in it, every code is one the question defines, and every timestamp,
duration and page number is written as its format says. A program does not
have to check this.
