# south

Fixed-width text, one record per line.

- `#LAYOUT <name>` names the layout of the lines that follow. The layouts are
  described in `/app/docs/layouts/<name>.txt`. A file starts with a layout line,
  and a long export can switch layout part way through with another one.
- `#SEQ N` gives the sequence number. `#END N` closes the file.
- The listing is paginated for printing: every page after the first starts
  with a line holding a form feed character and a `SOUTH DEPOT SHIPMENT
  LISTING ... PAGE n` heading.
- The record type (new, correction, void) and the status are one-letter codes
  whose positions depend on the layout.
