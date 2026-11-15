# Changelog of the table rules

## 3.0 (2027-02)

- A complete row is a speeder below 40 percent of the median duration of its
  form version (`cleaning.md` 3.2). Up to 2.x the threshold was half the
  median, and the short version 1 form lost careful respondents who read
  fast.
- Each form version has its own median (`cleaning.md` 3.1). Up to 2.x one
  median was taken over all complete rows, which made most rows of the
  shortest form look fast.
- Trimming is done once, after raking, and the weights are then scaled to a
  mean of 1 (`weighting.md` 3). Up to 2.x weights were trimmed after every
  raking iteration.

## 2.2 (2026-10)

- Targets are relative sizes and are turned into shares per dimension
  (`weighting.md` 1.2), so census counts can be pasted as they are. Up to 2.1
  every target had to be a percentage.
- A respondent without a category on a dimension keeps their weight while
  that dimension is adjusted (`weighting.md` 2.2). Up to 2.1 such
  respondents were dropped from the weighted results.

## 2.1 (2026-06)

- Duplicates: a complete row beats a partial row whatever their times
  (`cleaning.md` 1.2). Up to 2.0 the latest row won, so a respondent who
  opened the link again after finishing lost their answers.
- Times of version 1 exports are local times (`codebook.md` 2.4); they are
  compared with the other versions as instants.

## 2.0 (2026-03)

- Multiple choice answers with "None of these" and other options keep the
  other options (`codebook.md` 4.4).
- Answers to questions a respondent was routed away from are discarded
  (`codebook.md` 5.3); they used to be tabulated.
