# The tables file

## 1. Shape

1.1 The tables file is one JSON object:

    {
      "survey": "Residents survey 2027",
      "summary": {
        "versions": [
          {"version": "1", "rows": 806, "duplicates": 41, "short_partials": 30,
           "speeders": 22, "complete": 655, "partial": 58}
        ],
        "respondents": 2117,
        "effective_n": 1580.42,
        "weight_min": 0.36,
        "weight_max": 3.41
      },
      "tables": [
        {
          "table": "satisfaction",
          "columns": [
            {"column": "total", "base": 1984, "weighted_base": 1979.6,
             "values": {"1": 4.1, "2": 15.83, "3": 35.02, "4": 31.7, "5": 13.35,
                        "satisfied": 45.05, "mean": 3.34}},
            {"column": "region:1", "base": 0, "weighted_base": 0,
             "values": {"1": null, "2": null, "3": null, "4": null, "5": null,
                        "satisfied": null, "mean": null}}
          ]
        }
      ]
    }

1.2 Layout, indentation and key order inside an object are free; the file is
read as JSON. Extra keys are not allowed. The order of lists is part of the
result.

## 2. Summary

2.1 `survey` is the `survey` of the codebook.

2.2 `versions` has one entry per form version of the codebook, in codebook
order, also for a version without rows. `version` is the version key.
`rows` counts the rows of that version in all exports; `duplicates`,
`short_partials` and `speeders` count the rows of that version dropped by
`cleaning.md` 1, 2 and 3; `complete` and `partial` count the kept
respondents whose row is of that version. For every version, `rows` equals
the sum of the other five counts.

2.3 `respondents` is the number of kept respondents. `effective_n` is the
effective sample size of the final weights, `(sum of w) ** 2 / (sum of
w ** 2)`. `weight_min` and `weight_max` are the smallest and largest final
weight. With no kept respondent these three are null.

## 3. Tables

3.1 `tables` has one entry per table of the plan, in plan order. `table` is
the table `id`.

3.2 `columns` has one entry per banner column, in the order of `tables.md`
1. `base` is a whole number, `weighted_base` a number, and `values` an
object with one key per row of `tables.md` 3: option codes as text, then net
ids, then `mean` when the table has one.

## 4. Numbers

4.1 Every number that is not a count (`weighted_base`, percentages, means,
`effective_n`, `weight_min`, `weight_max`) is rounded to 2 decimals.

4.2 The research team compares tables files to 0.01: two files agree when
every count and every null is the same and every other number differs by at
most 0.01.
