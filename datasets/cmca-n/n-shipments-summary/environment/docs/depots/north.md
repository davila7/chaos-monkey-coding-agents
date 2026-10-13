# north

Family: JSON Lines.

- The first line is the metadata object
  `{"meta": {"depot": "north", "seq": N}}`.
- Record fields: `id` (for example `SH-012345`), `kind` (`new`, `amend` for a
  correction, `void`; a record without `kind` is new), `shipped_at`, a weight
  field, `status` and an optional `note`.
- The weight field's name gives its unit: `weight_<unit>`.
- `shipped_at` is an ISO 8601 time with a UTC offset (`Z` means UTC).
- Status values: `delivered`, `delivered_late`, `cancelled`, `returned`, `held`.
- A void record has only `id` and `kind`.
