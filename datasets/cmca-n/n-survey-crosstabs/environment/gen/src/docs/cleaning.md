# Cleaning

Cleaning decides which rows are kept. It runs in the order of this note:
duplicates first, then short partials, then speeders. Each dropped row is
counted once, under the step that dropped it and the form version of the row
(`output.md` 2).

## 1. One row per respondent

1.1 All rows of a respondent, from every file and every form version, are
compared together, and exactly one of them is kept.

1.2 A complete row beats a partial row, whatever their times.

1.3 Among rows of the same status, the row with the latest `submitted` time
wins (`codebook.md` 2.4: times are compared as instants, not as text).

1.4 Two rows of a respondent with the same status and the same instant are
copies of one submission exported twice; either one is kept.

1.5 The other rows of the respondent are dropped as duplicates.

## 2. Short partials

2.1 A kept partial row whose `last_page` is less than `partial_min_page` of
the codebook is dropped as a short partial.

2.2 Partial rows that reach `partial_min_page` are kept. They count for the
questions they were asked (`codebook.md` 5.1) and are weighted like complete
rows.

## 3. Speeders

3.1 For each form version, take the durations of the complete rows of that
version that are still kept after rules 1 and 2. Their median is the middle
value, or the mean of the two middle values when there is an even number.

3.2 A complete row is a speeder when its duration is less than 40 percent of the median of its form version, that is `duration * 5 < median * 2`.

3.3 Speeders are dropped. A partial row is never a speeder, and partial rows
do not enter the median.

3.4 Dropping a row as a speeder does not bring back a row of the same
respondent that rule 1 dropped as a duplicate: that respondent then has no
kept row.

## 4. Kept respondents

The rows left after rule 3 are the kept respondents, one row each. Only they
are weighted and tabulated.
