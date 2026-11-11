# merge (release 3.2)

`merge` finds the records in `members.json` that belong to one person and
merges each set into one record. Sections 2 to 4 say which records belong
together, sections 5 and 6 what the merged record holds, sections 7 to 9
what the command prints and writes.

## 1. The command

    python -m clubroll [--data DIR] [--by NAME] [--now TIME] merge [--apply]

Without `--apply` the command prints the plan (section 7) and writes
nothing. With `--apply` it prints the same plan and writes the files of
section 9. When there is no group to merge, nothing is written either way.

Errors: a missing or unreadable `settings.json` is a `DataError` with code
`settings`. A missing `keep_apart.csv` means no pair is kept apart by the
secretary; a `keep_apart.csv` with another header, a row without exactly
three fields, or an id that is not a member id (`ids.number` gives None) is
a `DataError` with code `keep-apart`. An `updated` value in none of the
forms of `data.md`, section 2, is a `DataError` with code `members`.

## 2. Comparison keys

Records are compared through keys made from their fields. The keys are for
comparing only; the merged record keeps values as they were entered
(section 6).

2.1 The name key: decompose the name (Unicode NFKD), drop the combining
marks, case fold, turn every character that is not a letter or a digit into
a space, and join the words with single spaces. `Zoë O'Neill`,
`ZOE O NEILL` and ` zoe  o-neill` all give `zoe o neill`; `Zoe ONeill`
gives `zoe oneill`. The given name is the first word of the name key.

2.2 The email key, with the settings of `data.md`, section 7:

1. Strip spaces at both ends and write the address in lower case.
2. An address without exactly one `@` has no key (`""`).
3. Replace the domain (after the `@`) by its target when it is a key of
   `domain_aliases`.
4. Cut the local part (before the `@`) at its first `+`, if any.
5. When the domain is in `dotless_domains`, remove every `.` from the local
   part.
6. An empty local part or domain gives no key.

2.3 The phone key, with the settings of `data.md`, section 7:

1. Remove every `(0)`, then drop every character that is not a digit or `+`.
2. Starting with `+`: the key is the digits after it. A `+` anywhere else
   gives no key.
3. Otherwise, starting with `00`: the key is the digits after `00`.
4. Otherwise, starting with `trunk`: the key is `country` followed by the
   digits after the trunk prefix.
5. Otherwise the number is incomplete and gives no key.
6. A key with fewer than 9 or more than 15 digits is no key.

`+44 7700 900123`, `0044 7700900123`, `+44 (0)7700-900-123` and
`07700 900123` (country `44`, trunk `0`) all give `447700900123`.

2.4 The birth day is `dob` read as a day; an empty `dob` is unknown.

## 3. Matching pairs and pairs kept apart

A pair of members matches by the first of these rules that holds:

| Rule | Holds when |
|---|---|
| `email` | the email keys are equal and not empty, and the given names are equal and not empty |
| `name-dob` | the name keys are equal and not empty, and both birth days are known and equal |
| `phone-name` | the name keys are equal and not empty, and the phone keys are equal and not empty |

Two members are kept apart when both birth days are known and differ, or
when a row of `keep_apart.csv` names them, in either order. The ids of a
row are looked up in `aliases.json` as it is before the merge; a row whose
two ids stand for the same member, or one of whose ids names no member, is
ignored.

## 4. Groups

Every member starts in a group of its own. The matching pairs are taken in
this order: by rule (`email`, then `name-dob`, then `phone-name`), then by
the lower member number of the pair, then by the higher. For each pair:

- when both members are already in the same group, nothing happens;
- when any member of one of the two groups is kept apart from any member of
  the other, the pair is refused and the groups stay as they are;
- otherwise the two groups become one.

A group of two or more members is merged. Two members that do not match
each other still end up in one group when each matches a third member,
unless a refusal (the second case above) keeps the groups apart. A group's
rules are the rules of the pairs that joined groups into it, each once, in
the order of the table in section 3.

## 5. The survivor and the precedence order

The survivor of a group is the member who joined first (`joined`, read as a
day); on the same day, the lower member number. The survivor keeps its
number and its record; the other members of the group are merged into it.

The precedence order of a group lists its members by `updated`, the latest
first (times compare as instants, `data.md`, section 2); on the same instant
the lower member number comes first.

## 6. The merged record

The survivor's record, with these fields set:

| Field | Value |
|---|---|
| `id`, `joined` | the survivor's |
| `name` | the survivor's; when it is empty, the first non-empty name in precedence order |
| `email`, `phone`, `dob` | the first non-empty value in precedence order, as it was entered; `""` when every member has `""` |
| `expires` | the latest day of the group; `""` when every member has `""` |
| `marketing` | the first non-empty value in precedence order, so the latest answer counts; `""` when every member has `""` (consent review MKT-3318) |
| `tags` | every tag of every member (`members.tag_list`), each once, sorted, as a list |
| `updated` | the command's time (`dates.stamp`), as for every change |

A field has changed when the value written differs from the survivor's
value before the merge; a list of tags never equals a tag string of the
2019 import. The source of a changed `name`, `email`, `phone` or `dob` is
the member the value came from; the source of a changed `expires` is the
first member in precedence order whose `expires` is the latest day.

## 7. Output

For each merged group, by survivor number:

    merge M-0003 <- M-0042, M-1003 (email, phone-name)
      email: "anna@example.org" -> "anna.k@example.org"
      tags: ["swim"] -> ["junior", "swim"]

The first line names the survivor, the merged members by number and the
group's rules. Then one line per changed field, in the order `name`,
`email`, `phone`, `dob`, `expires`, `marketing`, `tags`, `updated`, with the
values before and after written as JSON (Python's `json.dumps` with its
default separators and `ensure_ascii=False`).

Then, for each refused pair in the order the pairs were taken (section 4):

    kept apart M-0012 M-0077 (email)

with the lower number first and the pair's rule. Then the summary:

    3 groups, 5 members merged, 2 pairs kept apart

and, without `--apply`, a last line `dry run: nothing written`.

## 8. Audit lines

With `--apply`, one `merge` line per group, in the order of section 7,
numbered as `data.md`, section 6, says:

    {"seq":5121,"at":"2026-11-02T09:15:00Z","op":"merge","by":"cli","member":"M-0003","merged":["M-0042","M-1003"],"rules":["email","phone-name"],"changes":{...},"from":{...}}

`member` is the survivor, `merged` the merged members by number, `rules`
the group's rules, `changes` maps each changed field to `[before, after]`
in the order of section 7, and `from` maps each changed `name`, `email`,
`phone`, `dob` and `expires` to its source (section 6), in the same order.

## 9. Files written with --apply

- `members.json`: the merged members' records are removed and each
  survivor's record is replaced by the merged record (`members.save`).
- `aliases.json`: every merged member maps to its survivor, and every
  existing entry that pointed at a merged member now points at that
  member's survivor, so no alias points at another alias
  (`aliases.save`).
- `payments.csv`: a row whose `member`, looked up in `aliases.json` as it
  was before the merge, is a merged member gets the survivor's id
  (`ids.fmt`). Every other row is written as it was (`payments.save`).
- `audit.jsonl`: the lines of section 8 are appended.
