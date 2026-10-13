# Handovers between depots

A parcel that is handed over between depots is exported by both of them. The
records describe the same shipment but can disagree on weight, date and status,
because each depot records what it saw.

Handovers are resolved after each depot's own exports have been applied (see
`corrections.md`). When the same shipment number is among the current records
of more than one depot, keep exactly one record: the one from the depot that
comes first in this order.

1. central
2. south
3. east
4. river
5. north
6. west
7. harbor
8. lakeside

The kept record alone decides the depot the shipment is credited to, its
weight, its month and whether it is counted. If the kept record is not counted
(for example, it is cancelled), the shipment is not counted at all, even when
another depot's record says delivered.

`handovers` is the number of shipment numbers that are among the current
records of more than one depot, whatever their status.
