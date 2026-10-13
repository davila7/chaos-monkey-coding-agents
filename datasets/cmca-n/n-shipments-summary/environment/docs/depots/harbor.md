# harbor

Pipe-separated text with a header row.

- The first line is a comment of the form `#harbor export seq=N`. The last line
  is a `#rows=N` comment.
- Columns: `rec` (`NEW`, `COR` for a correction, `VOID`), `ref` (id, for example
  `SH:123456`), `date` (ship date, ISO), `weight` and `state`.
- Each weight names its own unit after a space: `12.50 kg`, `27.60 lb`, `880 g`,
  `14.5 oz`. Most rows are in kilograms.
- State codes: `DLV` delivered, `DLL` delivered late, `CAN` cancelled, `RET`
  returned, `HLD` held.
- A void row has only `rec` and `ref`.
- Harbor compresses some of its exports with gzip before sending them.
