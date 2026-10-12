# Duplicate shipments

A parcel that is handed over between depots is exported by both of them. The
two records describe the same shipment, but they can disagree on weight, date
and status, because each depot records what it saw.

When the same shipment number appears in more than one export, keep exactly one
record: the one from the export that comes first in this order.

1. central
2. south
3. east
4. river
5. north
6. west

Every other record of that shipment is dropped. The kept record alone decides
the depot the shipment is credited to, its weight, its month and whether it is
counted. If the kept record is not counted (for example, it is cancelled), the
shipment is not counted at all, even when a dropped record says delivered.

`duplicates_resolved` is the number of shipment numbers that appear in more
than one export, whatever the status of their records.
