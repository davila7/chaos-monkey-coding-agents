# Data files

Everything lives in the data directory (`--data`, default `data`).

## 1. Member ids

A member id is `M-` and the member number. clubroll writes ids with at
least four digits (`M-0042`, `ids.fmt`), and `members.json` holds them in
that form. People and older releases type ids in other forms (`M-42`,
`m-0042`, with spaces around); `ids.number` reads every form. Ids compare
by number.

## 2. Days and times

A day is written `YYYY-MM-DD`. The records imported from the old
spreadsheet in 2019 (tag `import-2019`) write `dob` and `joined` as
`DD/MM/YYYY`. `dates.parse_day` reads both forms. `expires` is always
`YYYY-MM-DD`. Days compare as days.

The `updated` time of a record has one of three forms:

| Form | Written by |
|---|---|
| `YYYY-MM-DDTHH:MM:SSZ` | clubroll (`dates.stamp`), and the register before 2023 |
| `YYYY-MM-DDTHH:MM:SS+HH:MM` (or `-HH:MM`) | the front desk app since 2023: local time with its offset from UTC |
| `YYYY-MM-DD` | the 2019 import, which kept only the day; it stands for 00:00:00 UTC that day |

Times compare as instants, whatever their form.

## 3. The register, `members.json`

    {"format": 3, "members": [ {record}, ... ]}

| Field | Value |
|---|---|
| `id` | the member id, `M-NNNN` |
| `name` | the full name as it was entered |
| `email` | the email address as it was entered, or `""` |
| `phone` | the phone number as it was entered, or `""` |
| `dob` | date of birth (a day, section 2), or `""` when not known |
| `joined` | the day the person joined the club (a day, section 2); never empty |
| `expires` | the last day the membership is paid for, or `""` when nothing was paid |
| `marketing` | consent to club mailings: `yes`, `no` (refused), or `""` (never asked) |
| `tags` | a list of strings; the 2019 import wrote one string with `;` between tags (`members.tag_list` reads both) |
| `updated` | when the record last changed (a time, section 2) |

Values are kept as they were entered: clubroll never rewrites a field it
did not change. `members.save` writes the records by member number, keys in
the order of the table, with an indent of 2 and non-ASCII characters as they
are, and a newline at the end.

## 4. Merged numbers, `aliases.json`

When two records were found to be one person, one of the numbers stopped
having a record. `aliases.json` maps each such number to the member it now
stands for:

    {"M-0005": "M-0019", ...}

Every value names a member that has a record in `members.json`: an alias
never points at another alias. Commands that take a member id look it up
here first (`aliases.resolve`, one step). Release 2 wrote the keys below
`M-0100` without leading zeros; `aliases.load` reads both forms and
`aliases.save` writes every id with `ids.fmt`, keys by number, with an
indent of 2 and a newline at the end.

## 5. Payments, `payments.csv`

Header `payment,member,day,amount`. `payment` is `P-` and five digits, in
the order the payments were recorded. `member` is the id as it was typed
when the payment was recorded, so it may be in any form of section 1 and
may name a number that is now in `aliases.json`. `pay` appends a row with
the id of the member, written with `ids.fmt`. `payments.save` writes the
rows in their order with Python's `csv` module, `\n` at the end of each line.

## 6. The audit log, `audit.jsonl`

One JSON object per line, written compact (`audit.dumps`: no spaces after
`,` and `:`, non-ASCII characters as they are). Keys in this order: `seq`,
`at` (the command's time, `dates.stamp`), `op`, `by`, `member`, then the
fields of the operation:

| `op` | Fields after `member` |
|---|---|
| `edit`, `renew` | `changes`: an object mapping each changed field to `[before, after]`, in the order of the table in section 3 |
| `pay` | `payment`, `amount` |

The log was rotated, so it does not start at 1, and `seq` may skip numbers.
A command that appends lines numbers them from the highest `seq` in the
file plus one (`audit.next_seq`), one after another. Release 3.2 adds
`merge` lines (`merge.md`, section 8).

## 7. Matching settings, `settings.json`

    {"phone": {"country": "44", "trunk": "0"},
     "email": {"dotless_domains": ["..."], "domain_aliases": {"...": "..."}}}

| Key | Meaning |
|---|---|
| `phone.country` | the club's country calling code, digits |
| `phone.trunk` | the prefix of a national number in that country, digits |
| `email.dotless_domains` | mail domains that ignore dots in the part before `@` |
| `email.domain_aliases` | mail domains that are another name of a domain: alias to domain |

All values are lower case. The file differs from club to club; never assume
its values. `merge.md`, section 2, says how they are used.

## 8. Pairs kept apart, `keep_apart.csv`

Header `first,second,note`. Each row names two members the secretary has
checked and found to be different people. Ids are written as people type
them (section 1) and may name a number that is now in `aliases.json`.
`note` is free text.
