# The codebook

`codebook.json` describes the survey, its form versions and its questions.

    {
      "survey": "Residents survey 2027",
      "reference_date": "2027-04-01",
      "partial_min_page": 2,
      "versions": {"1": {...}, "2": {...}, "3": {...}},
      "questions": [{...}, {...}]
    }

`survey` is the name of the survey. `reference_date` is the date ages refer
to (rule 4.6). `partial_min_page` is used by `cleaning.md` 2.

## 1. Questions

1.1 `questions` is a list, in the order the questions appear on the form.
Each question has an `id`, a `type` (`single`, `multi` or `age`) and a
`versions` object that says how each form version asked it (rule 3).

1.2 A `single` or `multi` question has `options`, a list of
`{"code": 3, "label": "South"}` objects in display order. An option can also
have:

- `"missing": true`: the code records a non-answer (don't know, prefer not to
  say). It is never part of a valid answer (rule 4.5).
- `"exclusive": true` (multi only): the option is meant to be chosen alone,
  such as "None of these" (rule 4.4).
- `"score": 4`: the value of the option in a mean (`tables.md` 4.3).

1.3 An `age` question has `bands` instead of options:
`{"code": 2, "label": "30-44", "min": 30, "max": 44}`, ages in whole years,
both ends included. Bands are its codes and play the part of options
everywhere else (banner columns, tables, weighting). No band is `missing`.

1.4 A question can have `ask_if` (rule 5.2).

## 2. Form versions

2.1 `versions` maps a version key (such as `"2"`) to a version. The
`form_version` cell of a row is that key as written. The order of `versions`
is the order of the form versions.

2.2 A version has `pages`, the number of pages of that form, and `meta`, the
columns that describe a row:

| Key | Meaning |
|---|---|
| `id` | column of the respondent id |
| `status` | column of the row status |
| `complete` | the status value of a complete row |
| `submitted` | column of the time the row was submitted or last saved |
| `submitted_format` | `iso` or `local` (rule 2.4) |
| `utc_offset` | with `local` only: the offset of the local times, `+HH:MM` or `-HH:MM` |
| `duration` | column of the time the respondent spent on the form |
| `duration_format` | `seconds` or `clock` (rule 2.5) |
| `last_page` | column of the last page the respondent reached |

2.3 A row is complete when its status cell equals `complete` exactly;
otherwise it is partial, whatever the status says. The respondent id is used
as written; ids are compared exactly.

2.4 `iso` times are ISO 8601 with a `T` between date and time and either `Z`
or an offset `+HH:MM` / `-HH:MM`: `2027-03-14T09:41:07Z`,
`2027-03-29T11:02:45+02:00`. `local` times are `YYYY-MM-DD HH:MM:SS` on the
clock of `utc_offset`: with `+01:00`, `2027-03-08 10:15:00` is
`2027-03-08T09:15:00Z`. Two times are compared as instants.

2.5 A `seconds` duration is a whole number of seconds. A `clock` duration is
`M:SS` or `H:MM:SS`: `9:05` is 545 seconds, `1:02:07` is 3,727.

2.6 `last_page` is a whole number. A complete row reached every page.

## 3. How a version asked a question

3.1 `versions` of a question maps a version key to how that version asked
it. A question that has no entry for a version was not on that form: no
respondent of that version was asked it.

3.2 Each entry has `page`, the page of that form the question was on, and
says where the answer is:

- `single` and `age`: `column`, the column of the answer.
- `multi`, one column per option: `columns`, mapping each option code (as
  text) to a column. An option is chosen when its cell is `1`; `0` or an
  empty cell means not chosen.
- `multi`, one column for all options: `column` and `separator`. The cell is
  a list of the chosen options separated by `separator`, in any order.

3.3 An entry can have `recode`, mapping the value as exported to the code.
Versions that export labels, or a scale in the other direction, have one.
Without `recode`, the value is the code written as a whole number.

3.4 An `age` entry has `source`, which says what the column holds (rule 4.6).

## 4. Reading an answer

4.1 Reading applies only to a question the respondent was asked (rule 5).
Anything in the cells of a question the respondent was not asked is
discarded.

4.2 `single`: an empty cell is no answer. Otherwise the value, through
`recode` if the entry has one, is the code.

4.3 `multi`: the chosen codes (rule 3.2). In a list, spaces around each
element are not part of it, empty elements are skipped, each element goes
through `recode` if the entry has one, and a code listed twice counts once.
No chosen code is no answer.

4.4 A multiple choice answer that has an exclusive option together with at
least one option that is not exclusive keeps the options that are not
exclusive and drops the exclusive ones. An answer of two or more exclusive
options and nothing else is no answer.

4.5 Codes marked `missing` are then removed. A single choice answer with a
missing code, or a multiple choice answer with nothing left, has no valid
answer.

4.6 `age`, by `source`:

- `band`: the value, through `recode`, is the band code.
- `age`: the value is the age in whole years.
- `birth_year`: the value is a year; the age is the year of
  `reference_date` minus the birth year.

An age is in the band with `min <= age <= max`. An age in no band, or an
empty cell, is no answer.

## 5. Routing

5.1 A kept respondent was asked a question when all of these hold:

1. the question has an entry for the respondent's form version (rule 3.1);
2. the respondent's row is complete, or the question's `page` for that
   version is at most the row's `last_page`;
3. the question has no `ask_if`, or its `ask_if` holds (rule 5.2).

5.2 `ask_if` is `{"question": "uses_transit", "codes": [1]}`. It holds when
the respondent was asked that earlier question and has a valid answer to it
that is one of `codes` (single choice, age) or that contains at least one of
`codes` (multiple choice). Otherwise it does not hold, also when the earlier
question was itself not asked.

5.3 The platform keeps what a respondent entered on a page they later routed
away from, and some versions fill cells of pages a partial respondent never
reached. Those cells are not answers (rule 4.1).
