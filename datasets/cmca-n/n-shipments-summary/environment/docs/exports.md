# Export conventions

The depots run several generations of export stations and office systems. The
conventions below are shared: each one can appear in any export of any depot
whose format family it fits, from the first line or from part way through a
file. A script that handles a convention for one depot only will be wrong on
other exports.

## Bytes and text

- An export can be gzip-compressed, whatever its name. A gzip stream starts with
  the bytes `1f 8b`; decompress it and read the result like any other export.
- Text is UTF-8 unless the file starts with a byte order mark or declares
  another character set. A byte order mark selects UTF-8 (`ef bb bf`) or UTF-16
  (`ff fe` little endian, `fe ff` big endian) and is not part of the text. A
  `# charset: <name>` directive near the top of a file names the encoding of
  the whole file.
- Lines end with a line feed. Blank lines carry nothing.

## Format families

Each depot note names the family of its base format.

### Delimited text

One record per row, fields separated by the depot's delimiter. Comma-separated
exports quote fields as usual for CSV (a field that contains a comma, a quote
or a line break is wrapped in double quotes, and a quoted field can span
lines). Exports with other delimiters never quote.

- **Comments and directives.** A `#` at the start of a line, outside a quoted
  field, starts a comment line. A comment of the form `# name: value` is a
  directive. A directive applies to the rows after it, up to the next directive
  with the same name; any directive can appear again anywhere in a file.
- **Header rows.** A row whose fields are all column names of the depot is a
  header row. Header rows can appear again anywhere in a file, with or without a
  comment announcing them, and can list the columns in a different order. Each
  row is read with the most recent header row above it.
- **Field count.** A record row has as many fields as the header row in force,
  except rows that carry their own weight unit (see Weights below).
- **Trailers.** Total rows and count lines at the end of a file are not
  records.

### Fixed-width text

Each record line follows a named layout described in `/app/docs/layouts/`. A
layout line (`#LAYOUT <name>`) names the layout of the lines after it. Every
layout has its own record length, given in its description. Some stations
switch layout without writing a layout line: a record line whose length is not
the record length of the layout in force was written in the layout that has
that length. Page headers of printed listings are not records.

### XML

One root element per file. Attributes of the root element give file-wide values
(sequence number, schema, file-wide units). An attribute or child element of a
record gives that record's own value and wins over the root.

### JSON Lines

One JSON value per line: an object or an array of objects. Each object is one
record unless it is the file's metadata object.

## Values

### Weights

A weight's unit is decided by the most specific declaration that applies to it:

1. a unit written with the value itself or named by its field (a unit suffix,
   a `unit` attribute, a field name that ends in a unit);
2. a unit that the row itself carries. Stations that record a unit for each
   row add it to the row without writing a new header row;
3. the unit directive or root attribute in force;
4. the base unit given in the depot note.

Units are `kg`, `g`, `lb` and `oz`; conversion factors are in
`summary-format.md`. Thousands separators and decimal marks follow the depot
note.

### Dates and times

A date field is read in the form declared by the date directive in force, or in
the depot's base form when no directive has been given. Forms in use:

- `iso` and `YMD`: `2026-03-04`
- `DMY`: `04-03-2026`
- `MM/DD/YYYY` and `DD/MM/YYYY`
- `serial`: a spreadsheet day number, where day 1 is 1899-12-31, so 46085 is
  2026-03-04
- the fixed forms named in a depot note or layout (`16 Mar 2026`,
  `DD.MM.YYYY`, `YYYYDDD`, `YYYYMMDD`)

How the month of a ship date or ship time is decided is in `summary-format.md`.
