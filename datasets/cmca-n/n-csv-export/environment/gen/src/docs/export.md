# tally export: specification

Status: approved for release 1.9. The command does not exist yet in 1.8.

`export` writes the records of one collection as CSV text. Downstream systems
load these files byte for byte, so every rule below is part of the contract:
two implementations that follow this note produce identical bytes for the
same store and the same options.

## 1. Synopsis

    python -m tally [--store DIR] export COLLECTION
        [--columns SPEC] [--where EXPR] [--sort SPEC]
        [--locale NAME] [--no-grouping]
        [--delimiter CHAR] [--null TOKEN] [--no-header]
        [--out PATH] [--max-rows N]

The command follows the conventions of the other commands
(`docs/conventions.md`): it is registered in the command list, reads the store
only through the store API, reports usage problems as errors with exit status
2, and writes files through the shared output helpers.

## 2. Processing order

1. Check every option (section 9). Nothing is read or written before all
   options are known to be valid.
2. Take the live records of the collection in store order
   (`docs/store.md`, section 4).
3. Keep the records for which `--where` holds (section 5).
4. Sort them by `--sort` (section 6).
5. Turn each record into one CSV record of the selected columns (sections 3,
   7 and 8).
6. Write the header and the records to standard output or to files
   (section 10).

## 3. Columns

3.1 `--columns` is a comma-separated list of items. Each item is either
`PATH` or `PATH=NAME`:

* `PATH` is the dotted name of a field of the collection's schema, such as
  `total` or `address.city`;
* `NAME` is the column name to write in the header instead of the path.

Whitespace around items, paths and names is ignored. A name keeps the spaces
inside it (`city = billing city` names the column `billing city`).

3.2 Without `--columns`, every field of the schema is exported, in schema
order, each named by its path.

3.3 A field may be exported more than once under different names. Two columns
with the same name, an empty path, an empty name, or a path that is not a field
of the schema are errors.

3.4 Columns are written in the order the items list them.

## 4. Values

4.1 Every value is read with its schema type (`docs/store.md`, section 3). A
missing value and a JSON null are both null.

4.2 Filters and sorting compare typed values: numbers as numbers (an `int`
field and a `decimal` field compare by value), dates and datetimes in time
order, strings by Unicode code point (so `"B" < "a"` and the comparison is
case-sensitive), booleans with `false` before `true`.

## 5. Filter expressions (`--where`)

5.1 Grammar. Keywords (`and`, `or`, `not`, `in`, `is`, `null`, `true`,
`false`) are matched without regard to case. Whitespace separates tokens and
is otherwise ignored.

    expr        := or_expr
    or_expr     := and_expr ( "or" and_expr )*
    and_expr    := not_expr ( "and" not_expr )*
    not_expr    := "not" not_expr | primary
    primary     := "(" expr ")" | test
    test        := PATH op literal
                 | PATH "is" "null"
                 | PATH "is" "not" "null"
                 | PATH "in" "(" literal ( "," literal )* ")"
                 | PATH "not" "in" "(" literal ( "," literal )* ")"
    op          := "=" | "!=" | "<" | "<=" | ">" | ">=" | "~"
    literal     := STRING | NUMBER | "true" | "false"

* `PATH` is a field path as in section 3: letters, digits, `_` and `.`,
  starting with a letter or `_`. A keyword is never a path.
* `STRING` is enclosed in single quotes. A single quote inside the string is
  written as two single quotes (`'O''Brien'`). There are no other escapes; a
  backslash is an ordinary character.
* `NUMBER` is an optional `-`, one or more digits, and optionally a `.`
  followed by one or more digits.

`not` binds tighter than `and`, and `and` binds tighter than `or`:
`a = 1 or b = 2 and not c = 3` means `a = 1 or (b = 2 and (not c = 3))`.

5.2 Literal kinds. The literal of a test must suit the field's type:

| Field type | Literal | Comparison |
|---|---|---|
| `int`, `decimal` | NUMBER | numeric |
| `string` | STRING | code point order |
| `date` | STRING holding `YYYY-MM-DD` | time order |
| `datetime` | STRING holding `YYYY-MM-DDTHH:MM:SSZ`, or `YYYY-MM-DD` meaning 00:00:00 of that day | time order |
| `bool` | `true` or `false` | only `=` and `!=` |

Any other pairing is an error, as are `<`, `<=`, `>`, `>=` on a `bool`
field, `~` on a field that is not a `string`, and a STRING that does not hold
a valid date or datetime for a temporal field. The test `PATH = null` does not
exist; nulls are tested with `is null` and `is not null`.

5.3 `~` holds when the field's text contains the literal's text
(case-sensitive). `in` holds when the value equals one of the literals.

5.4 Nulls. A test of `=`, `!=`, `<`, `<=`, `>`, `>=`, `~`, `in` or `not in`
on a null value is **false**. `is null` is true exactly for null values and
`is not null` exactly for the others. `not` turns true into false and false
into true; there is no third truth value. So `status != 'open'` leaves out
records with a null status, while `not status = 'open'` keeps them.

5.5 Without `--where`, every record is kept.

## 6. Sorting (`--sort`)

6.1 `--sort` is a comma-separated list of sort keys:

    PATH[:asc|:desc][:nulls-first|:nulls-last]

The direction comes before the null placement when both are given. Without a
direction the key is ascending. The words are lower case.

6.2 Records are ordered by the first key; records equal on it by the second
key, and so on. Records equal on every key keep their relative order from the
step before (the store order, after filtering): the sort is stable.

6.3 Null placement. When a key gives `nulls-first` or `nulls-last`, null
values of that key come before or after every non-null value, whatever the
direction. When a key gives no placement, nulls sort as if they were larger
than every value: last for an ascending key, first for a descending key.

6.4 A sort key may name any field of the schema, exported or not. A path that
is not a field, a repeated path, or a malformed key is an error.

6.5 Without `--sort`, records stay in store order.

## 7. Text of a value

7.1 Without `--locale`, values are written in their canonical form:

| Type | Text |
|---|---|
| `string` | the string itself |
| `int` | decimal digits, with `-` for negative numbers, no grouping |
| `decimal` | digits, `.`, exactly `scale` fraction digits, `-` for negative numbers, no grouping |
| `bool` | `true` or `false` |
| `date` | `YYYY-MM-DD` |
| `datetime` | `YYYY-MM-DDTHH:MM:SSZ` |

7.2 With `--locale NAME`, numbers, booleans, dates and datetimes follow the
locale's entry in the locale table (`docs/locales.md`). Strings are never
changed by a locale.

* An `int` is its digits, grouped (7.3), with the locale's `minus` before it
  when negative.
* A `decimal` is its integer digits, grouped, then the locale's `decimal`
  separator and exactly `scale` fraction digits, with the locale's `minus`
  before it when negative. A value whose digits are all zero is never
  negative.
* A `bool` is the locale's `true` or `false` text.
* A `date` follows the locale's `date` pattern and a `datetime` its
  `datetime` pattern (7.4). Datetimes are written in UTC as stored; there is
  no time zone conversion.

7.3 Grouping. The integer digits are split into groups from the right using
the locale's `group_sizes`: the first size is the size of the rightmost
group, each following size the size of the next group to the left, and the
last size repeats for every further group. Groups are joined with the locale's
`group` text. Grouping applies only when the integer part has at least
`group_sizes[0] + min_grouping` digits; shorter integer parts are written
without separators. `--no-grouping` turns grouping off for every value; it
has no effect without `--locale`.

7.4 Date patterns. A pattern is read from left to right; at each position the
longest token that matches is replaced, and any other character is copied as
it is.

| Token | Meaning |
|---|---|
| `YYYY` | year, four digits |
| `MM` / `M` | month, two digits / without leading zero |
| `DD` / `D` | day of the month, two digits / without leading zero |
| `HH` / `H` | hour 0 to 23, two digits / without leading zero |
| `hh` / `h` | hour 1 to 12, two digits / without leading zero |
| `mm` | minute, two digits |
| `ss` | second, two digits |
| `A` | `AM` for hours 0 to 11, `PM` for hours 12 to 23 |

On the 12-hour clock, hour 0 is 12 AM and hour 12 is 12 PM. A date pattern
that a `date` value is formatted with uses only the date tokens.

## 8. CSV text

8.1 Records are separated by CR LF: every record, the header and the last
record included, ends with the two characters `\r\n`.

8.2 Fields are separated by the delimiter: `,` unless `--delimiter` gives
another single character. `--delimiter tab` means the tab character. The
delimiter must not be `"`, CR, LF or a space.

8.3 Null values are written as the null token: the empty text unless `--null`
gives another one. The null token is written as it is, never quoted. A null
token must not contain the delimiter, `"`, CR or LF.

8.4 Every other field (header names included) is written as its text from
section 7, enclosed in double quotes when it needs to be, and only then. A
field needs quotes when its text

* contains the delimiter, a double quote, CR or LF; or
* begins or ends with a space or a tab; or
* is equal to the null token (so that a reader can tell a value from a null;
  with the empty null token this means every empty string value is written
  as `""`).

Inside quotes, every double quote is written twice. Nothing else is escaped.

8.5 The text is encoded as UTF-8 without a byte order mark.

8.6 The header is one record holding the column names (section 3). It is
written first unless `--no-header` is given.

## 9. Errors

9.1 Each of these is a usage error (exit status 2, a message on standard
error, nothing written to standard output, no file created or changed):

* an unknown collection;
* any problem with `--columns`, `--where` or `--sort` named in sections 3, 5
  and 6;
* an unknown locale;
* an invalid delimiter or null token (section 8);
* `--max-rows` below 1, or `--max-rows` without `--out` (or with `--out -`).

9.2 A store that cannot be read is a store error (exit status 3), as for every
command.

## 10. Output

10.1 Without `--out`, or with `--out -`, the CSV text is written to standard
output.

10.2 With `--out PATH`, the CSV text is written to the file `PATH` (missing
parent directories are created; an existing file is replaced).

10.3 Splitting. With `--max-rows N`, the records (not counting the header)
are written to numbered files of at most `N` records each, when there are
more than `N` records. The files are named after `PATH` with `-` and a
sequence number inserted before the suffix: `out/orders.csv` becomes
`out/orders-001.csv`, `out/orders-002.csv`, and so on; a `PATH` without a
suffix gets the number at its end (`out/orders` becomes `out/orders-001`).
The suffix is everything from the last `.` of the file name, when the name has
a `.` that is not its first character. Numbers have three digits, or as many
as the number of the last file needs. Every file but the last holds exactly
`N` records, and every file starts with the header unless `--no-header` is
given. `PATH` itself is not written.

10.4 When there are `N` records or fewer, including none, a single file
`PATH` is written as without `--max-rows`. With no records it holds only the
header (or nothing, with `--no-header`).

10.5 The command prints nothing on standard output when it writes files.
