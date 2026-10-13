# north

JSON Lines: one JSON value per line. Blank lines can occur and carry nothing.

- The first line is `{"meta": {"depot": "north", "seq": N}}`.
- Every other line holds either one record object or an array of record
  objects (north batches records during busy periods).
- Record fields: `id` (for example `SH-012345`), `kind` (`new`, `amend` for a
  correction, `void`; a record without `kind` is new), `shipped_at`, a weight
  field, `status` and an optional `note`.
- The weight field's name gives its unit: `weight_kg`, `weight_g` or
  `weight_lb`.
- `shipped_at` is an ISO 8601 time with a UTC offset (`Z` means UTC). North
  ships across several time zones, so the local date and the UTC date often
  differ.
- A void record has only `id` and `kind`.
