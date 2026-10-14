# harbor

Family: delimited text, pipe-separated.

- The first line is a comment of the form `#harbor export seq=N`. The last line
  is a `#rows=N` comment.
- Columns: `rec` (`NEW`, `COR` for a correction, `VOID`), `ref` (id, for example
  `SH:123456`), `date` (ship date; base form `iso`), `weight` and `state`.
- Each weight names its own unit after a space: `12.50 kg`, `880 g`.
- State codes: `DLV` delivered, `DLL` delivered late, `CAN` cancelled, `RET`
  returned, `HLD` held.
- A void row has only `rec` and `ref`.
