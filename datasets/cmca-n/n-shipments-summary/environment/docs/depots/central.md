# central

Family: XML. Root element `<export>`.

- Root attributes: `seq` (sequence number), `schema` (1 or 2) and
  `weight-unit`, the unit of any weight that does not name its own.
- One `<shipment>` element per record, with the id in its `id` attribute (for
  example `SH-0123456`). A `type` attribute marks `correction` and `void`
  records; without it the record is new. A void record has no children.
- `<weight>` holds a number and can carry a `unit` attribute.
- Ship time: schema 1 puts the ship date in a `shipped` attribute of
  `<shipment>`, as `16 Mar 2026`. Schema 2 has a `<shipped>` child element with
  a full ISO 8601 time and UTC offset.
- `<status>` holds `delivered`, `delivered late`, `cancelled`, `returned` or
  `held`. `<note>` is free text.
- The closing `<summary count="..."/>` element is not a shipment.
