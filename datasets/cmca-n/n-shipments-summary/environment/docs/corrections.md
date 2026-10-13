# Corrections, voids and resends

Each depot sends many exports, and a later export can change what an earlier
one said.

## Export order

Every export carries a sequence number (`seq`), written inside the file; the
depot notes say where. Within one depot, apply the exports in ascending `seq`
order, and the records of one export from top to bottom. File names do not give
this order: weekly labels are not zero-padded, and a reissued export (label
ending in `r`) is sent after the weeks that follow it. Sequence numbers are only
compared between exports of the same depot.

## Record types

Within one depot, keep one current record per shipment number and apply each
record in export order:

- **new**: if the depot has no current record for the number, it becomes the
  current record. If it already has one, the new record is a resend of a
  shipment the depot already exported: drop it, whatever it says, and add one to
  `resends_dropped`. A resend never undoes a correction.
- **correction**: carries the full record and replaces the current record for
  that number (weight, ship time, status, everything). Add one to
  `corrections_applied`.
- **void**: removes the current record for that number; the depot no longer
  reports the shipment. Add one to `corrections_applied`.

When exports are applied in the right order, a correction or void always follows
a new record for the same number from the same depot.

After the last export of each depot, the current records are that depot's
shipments. Shipments that more than one depot reports are resolved next, in
`handovers.md`.
