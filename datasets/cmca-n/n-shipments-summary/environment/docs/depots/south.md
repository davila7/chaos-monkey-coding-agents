# south

Family: fixed-width text. Layouts are described in `/app/docs/layouts/`.

- `#LAYOUT <name>` names a layout, `#SEQ N` gives the sequence number and
  `#END N` closes the file.
- The listing is paginated for printing: every page after the first starts
  with a line holding a form feed character and a `SOUTH DEPOT SHIPMENT
  LISTING ... PAGE n` heading.
- The record type (new, correction, void), the ship date, the weight and its
  unit, and the status code are given by the layout.
