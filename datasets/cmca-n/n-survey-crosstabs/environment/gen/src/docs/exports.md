# Response exports

The survey platform exports responses as delimited text with one header line
and one line per row:

    form_version,respondent_id,status,submitted_at,duration_s,last_page,region,age,...
    2,R48213,complete,2027-03-14T09:41:07Z,702,4,3,57,...

## 1. Files

1.1 The exports are the regular files directly in `exports/` whose name ends
in `.csv`. Every other file there (logs, notes, unfinished downloads such as
`*.csv.part`) is not an export and is ignored.

1.2 Exports are UTF-8. A file can start with a byte order mark (`EF BB BF`),
which is not part of the header line.

1.3 Lines end with LF or with CR LF. Both can occur in one input directory.

## 2. Delimiters and quoting

2.1 The delimiter of a file is a comma, a semicolon or a tab. The header line
contains exactly one of the three, and that one is the delimiter of the whole
file. Different files can use different delimiters.

2.2 A cell that contains the delimiter, a double quote or a line break is
enclosed in double quotes, and a double quote inside it is written twice
(the usual CSV quoting). A multiple choice list such as `"1,4"` in a comma
file is one cell.

## 3. Header and cells

3.1 The header line names the columns. Spaces around a column name are not
part of it.

3.2 Each later line is a row with one cell per column. Spaces around a cell
are not part of it. An empty cell, or a cell of spaces only, has no value.

3.3 A line whose cells are all empty is not a row.

3.4 Every row has a `form_version` cell (`codebook.md` 2.1). One file can
hold rows of several form versions; then its header has the columns of all of
them, and the cells of columns a row's version does not use are empty.

3.5 A column that the codebook names for a row's version but that is not in
the file's header has no value for that row.

3.6 Column order is free and differs between files. Extra columns that the
codebook does not name are ignored.
