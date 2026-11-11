# Commands

Every command that takes a member id accepts any form of `data.md`,
section 1, and looks it up in `aliases.json` first. A malformed id is a
usage error (`bad-id`); an id that names no member is refused
(`unknown-member`).

## 1. show ID

Prints `NAME: VALUE` for every field of the record, in the order of
`data.md`, section 3; tags are joined with `, `. When the id is an alias, a
first line `M-0005 -> M-0019` names the member it stands for.

## 2. list [--tag TAG]

One line per member, by member number: the id, two spaces, `expires` (or
`-`) padded to 10 characters, two spaces, the name. `--tag` keeps the
members that carry the tag.

## 3. find TEXT

The `list` lines of the members whose name contains TEXT (compared with
spaces collapsed and case folded), whose email contains TEXT (compared in
lower case), or, when TEXT holds at least four digits, whose phone number
contains those digits. `contact.py` holds these keys; they are for searching
only.

## 4. edit ID FIELD VALUE

Sets one of `name`, `email`, `phone`, `dob`, `marketing` and prints
`M-0042 FIELD: BEFORE -> AFTER`. `dob` takes a day written `YYYY-MM-DD` or
`""`; `marketing` takes `yes`, `no` or `""`; a name cannot be empty. A value
equal to the current one prints `M-0042 FIELD unchanged` and writes
nothing. Otherwise `updated` is set and an `edit` line is appended to the
audit log.

## 5. renew ID DAY

Sets `expires` to DAY (`YYYY-MM-DD`), which must be later than the current
`expires` (`not-later`), prints `M-0042 expires DAY` and appends a `renew`
line.

## 6. pay ID AMOUNT [--day DAY]

Records a payment (AMOUNT with two decimals, more than 0, `bad-amount`
otherwise) on DAY, by default the UTC day of `--now`, appends a row to
`payments.csv` and a `pay` line to the audit log, and prints
`P-01234 M-0042 AMOUNT`.
