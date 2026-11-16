# Weighting

The kept respondents are weighted so that the weighted sample matches the
population on a few questions, by raking (iterative proportional fitting),
followed by one trimming step. `weighting.json` holds the settings:

    {
      "dimensions": [
        {"question": "region", "source": "...", "targets": {"1": 182400, "2": 141250}},
        {"question": "age_band", "source": "...", "targets": {"1": 19.5, "2": 24.8}}
      ],
      "max_iterations": 100,
      "tolerance": 1e-10,
      "cap": 3.5,
      "floor": 0.3
    }

## 1. Dimensions and targets

1.1 Each dimension names a `single` or `age` question of the codebook and
gives a target for some of its codes (keys are codes as text). `source` is a
note for people and is not used.

1.2 Targets are relative sizes. One dimension can give population counts,
another percentages or shares; only the ratios inside a dimension matter.
The targets of a dimension are turned into shares that add up to 1 by
dividing each by their sum.

1.3 A code with a target but no kept respondent whose valid answer is that
code is removed from the dimension before its targets are turned into shares
(rule 1.2).

1.4 A respondent has a category on a dimension when they have a valid answer
to its question and that code has a target (after rule 1.3). A respondent
with no valid answer, or with a code that has no target, has no category on
that dimension.

## 2. Raking

2.1 Every kept respondent starts with weight 1.

2.2 One iteration adjusts the dimensions one after another, in the order of
`dimensions`. To adjust a dimension:

1. `T` is the sum of the weights of the respondents that have a category on
   the dimension;
2. for each category `c`, `W_c` is the sum of the weights of its
   respondents, and its factor is `f_c = share_c * T / W_c`;
3. the weight of every respondent in category `c` is multiplied by `f_c`.
   Respondents without a category on the dimension keep their weight.

2.3 After each iteration, raking stops when every factor of that iteration
was within `tolerance` of 1 (`abs(f_c - 1) <= tolerance`). It stops after
`max_iterations` iterations in any case.

## 3. Trimming

3.1 After raking, let `m` be the mean weight of all kept respondents.

3.2 A weight above `cap * m` is set to `cap * m`; a weight below
`floor * m` is set to `floor * m`.

3.3 Then every weight is multiplied by the same number so that the mean
weight is exactly 1 (the weights add up to the number of kept respondents).
These are the final weights.

3.4 Trimming is done once. There is no raking after it, so the weighted
sample can be a little off the targets.

## 4. No respondents

With no kept respondent there are no weights; every table column then has a
base of 0 (`tables.md` 5).
