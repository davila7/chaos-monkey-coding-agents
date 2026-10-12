# central

XML, one `<export>` element per file.

- `<export>` attributes: `seq` (sequence number), `schema` (1 or 2) and
  `weight-unit`, the unit for any weight that does not name its own.
- One `<shipment>` element per record, with the id in its `id` attribute. A
  `type` attribute marks `correction` and `void` records; without it the record
  is new. A void record has no children.
- `<weight>` usually carries a `unit` attribute (`kg`, `lb` or `oz`). Some export
  runs leave it out for a stretch of records; those weights are in the export's
  `weight-unit`, which is not always `kg`.
- Ship time: schema 1 puts the ship date in a `shipped` attribute, as
  `16 Mar 2026`. Schema 2 has a `<shipped>` child element with a full ISO 8601
  time and UTC offset.
- `<status>` holds `delivered`, `delivered late`, `cancelled`, `returned` or
  `held`. `<note>` is free text.
- The closing `<summary count="..."/>` element is not a shipment.
