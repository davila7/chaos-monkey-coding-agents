# Tables

`tables.json` is the table plan:

    {
      "banner": ["region", "age_band"],
      "tables": [
        {"id": "satisfaction", "question": "satisfaction",
         "nets": [{"id": "satisfied", "codes": [4, 5]}], "mean": true},
        {"id": "transit_modes", "question": "transit_modes"}
      ]
    }

Every table has the same columns, the banner, and one row per option of its
question, then its nets, then its mean.

## 1. Banner columns

1.1 The first column is `total`: every kept respondent.

1.2 Then, for each banner question in the order of `banner`, one column per
option that is not `missing` (bands for an `age` question), in the order of
the codebook. The column id is the question id, a colon and the code:
`region:3`, `age_band:1`. A column exists even when no respondent is in it.

1.3 A respondent is in a banner column when their valid answer to the banner
question is the column's code. Banner questions are `single` or `age`. A
respondent with no valid answer to a banner question is in none of its
columns, but still in `total`.

## 2. Base

2.1 The base of a table is the kept respondents who were asked its question
(`codebook.md` 5) and have a valid answer to it. Respondents who were not
asked, who left it empty or who answered only with `missing` codes are not in
the base.

2.2 The base of a column is the respondents of the table base who are in the
column. `base` is their number and `weighted_base` the sum of their final
weights (`weighting.md` 3).

## 3. Rows

3.1 One row per option of the table's question that is not `missing`, in the
order of the codebook, keyed by the code as text. For a multiple choice
question, exclusive options that are not `missing` (such as "None of these")
get a row too.

3.2 Each net of the table gets a row after the options, keyed by the net
`id`. A respondent is in a net when their valid answer is one of its codes
(single choice) or contains at least one of them (multiple choice).

3.3 A table with `"mean": true` gets a last row keyed `mean`. Mean tables
are single choice questions whose non-missing options all have a `score`.

## 4. Values

4.1 The value of an option row is the weighted percentage of the column base
whose valid answer is that code (single choice) or contains it (multiple
choice): 100 times the sum of their weights, divided by `weighted_base`.

4.2 The value of a net row is the weighted percentage of the column base in
the net. A multiple choice respondent counts once in a net, however many of
its codes they chose.

4.3 The value of the mean row is the sum of weight times score over the
column base, divided by `weighted_base`.

4.4 Percentages of a multiple choice table can add up to more than 100.

## 5. Empty columns

A column with a base of 0 has `weighted_base` 0 and every value null.
